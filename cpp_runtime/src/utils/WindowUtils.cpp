#include "utils/WindowUtils.h"

#include <algorithm>
#include <cstdint>
#include <cwctype>
#include <filesystem>
#include <stdexcept>

namespace beavis::windows {

std::wstring utf8ToWide(const std::string& value) {
    if (value.empty()) {
        return {};
    }

    const int size = MultiByteToWideChar(
        CP_UTF8,
        MB_ERR_INVALID_CHARS,
        value.data(),
        static_cast<int>(value.size()),
        nullptr,
        0
    );
    if (size <= 0) {
        throw std::runtime_error("Failed to convert UTF-8 string to UTF-16");
    }

    std::wstring out(static_cast<size_t>(size), L'\0');
    const int written = MultiByteToWideChar(
        CP_UTF8,
        MB_ERR_INVALID_CHARS,
        value.data(),
        static_cast<int>(value.size()),
        out.data(),
        size
    );
    if (written <= 0) {
        throw std::runtime_error("Failed to convert UTF-8 string to UTF-16");
    }

    return out;
}

std::string wideToUtf8(const std::wstring& value) {
    if (value.empty()) {
        return {};
    }

    const int size = WideCharToMultiByte(
        CP_UTF8,
        0,
        value.data(),
        static_cast<int>(value.size()),
        nullptr,
        0,
        nullptr,
        nullptr
    );
    if (size <= 0) {
        return {};
    }

    std::string out(static_cast<size_t>(size), '\0');
    const int written = WideCharToMultiByte(
        CP_UTF8,
        0,
        value.data(),
        static_cast<int>(value.size()),
        out.data(),
        size,
        nullptr,
        nullptr
    );
    if (written <= 0) {
        return {};
    }

    return out;
}

std::wstring lower(std::wstring value) {
    std::transform(value.begin(), value.end(), value.begin(), [](wchar_t ch) {
        return static_cast<wchar_t>(std::towlower(ch));
    });
    return value;
}

std::wstring filenameOf(const std::wstring& value) {
    if (value.empty()) {
        return {};
    }

    try {
        return lower(std::filesystem::path(value).filename().wstring());
    } catch (...) {
        return {};
    }
}

namespace {
std::wstring getWindowTitle(HWND hwnd) {
    const int length = GetWindowTextLengthW(hwnd);
    if (length <= 0) {
        return {};
    }

    std::wstring title(static_cast<size_t>(length + 1), L'\0');
    const int written = GetWindowTextW(hwnd, title.data(), length + 1);
    if (written <= 0) {
        return {};
    }

    title.resize(static_cast<size_t>(written));
    return title;
}

std::wstring getProcessPath(DWORD processId) {
    HANDLE process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, processId);
    if (process == nullptr) {
        return {};
    }

    std::vector<wchar_t> buffer(32768);
    DWORD size = static_cast<DWORD>(buffer.size());
    const BOOL ok = QueryFullProcessImageNameW(process, 0, buffer.data(), &size);
    CloseHandle(process);

    if (!ok || size == 0) {
        return {};
    }

    return std::wstring(buffer.data(), static_cast<size_t>(size));
}

bool containsLower(const std::wstring& value, const std::wstring& needle) {
    if (value.empty() || needle.empty()) {
        return false;
    }

    return lower(value).find(lower(needle)) != std::wstring::npos;
}

BOOL CALLBACK enumWindowsProc(HWND hwnd, LPARAM lParam) {
    auto* windows = reinterpret_cast<std::vector<WindowInfo>*>(lParam);
    if (!isCandidateWindow(hwnd)) {
        return TRUE;
    }

    DWORD processId = 0;
    GetWindowThreadProcessId(hwnd, &processId);
    if (processId == 0) {
        return TRUE;
    }

    WindowInfo info;
    info.hwnd = hwnd;
    info.processId = processId;
    info.title = getWindowTitle(hwnd);
    info.processPath = getProcessPath(processId);
    info.processFile = filenameOf(info.processPath);

    windows->push_back(std::move(info));
    return TRUE;
}

int scoreWindow(const WindowInfo& window, const AppWindowTarget& target) {
    int score = 0;
    const std::wstring processPathLower = lower(window.processPath);
    const std::wstring titleLower = lower(window.title);

    if (!target.targetPath.empty() && processPathLower == lower(target.targetPath)) {
        score += 120;
    }

    if (!target.targetFile.empty() && window.processFile == target.targetFile) {
        score += 100;
    }

    if (!target.appIdWide.empty()) {
        if (window.processFile.find(target.appIdWide) != std::wstring::npos) {
            score += 45;
        }
        if (titleLower.find(target.appIdWide) != std::wstring::npos) {
            score += 25;
        }
    }

    if (!target.displayName.empty() && containsLower(window.title, target.displayName)) {
        score += 35;
    }

    return score;
}

bool activateWindow(HWND target) {
    if (target == nullptr || !IsWindow(target)) {
        return false;
    }

    HWND foreground = GetForegroundWindow();
    const DWORD currentThread = GetCurrentThreadId();
    const DWORD foregroundThread = foreground != nullptr
        ? GetWindowThreadProcessId(foreground, nullptr)
        : 0;
    const DWORD targetThread = GetWindowThreadProcessId(target, nullptr);

    const bool attachForeground = foregroundThread != 0 && foregroundThread != currentThread;
    const bool attachTarget = targetThread != 0 && targetThread != currentThread;

    if (attachForeground) {
        AttachThreadInput(currentThread, foregroundThread, TRUE);
    }
    if (attachTarget && targetThread != foregroundThread) {
        AttachThreadInput(currentThread, targetThread, TRUE);
    }

    BringWindowToTop(target);
    SetWindowPos(
        target,
        HWND_TOP,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    );

    const BOOL foregroundOk = SetForegroundWindow(target);
    SetActiveWindow(target);
    SetFocus(target);

    if (attachTarget && targetThread != foregroundThread) {
        AttachThreadInput(currentThread, targetThread, FALSE);
    }
    if (attachForeground) {
        AttachThreadInput(currentThread, foregroundThread, FALSE);
    }

    return foregroundOk != 0 || GetForegroundWindow() == target;
}
}

bool isCandidateWindow(HWND hwnd) {
    if (hwnd == nullptr || !IsWindow(hwnd) || !IsWindowVisible(hwnd)) {
        return false;
    }

    const LONG exStyle = GetWindowLongW(hwnd, GWL_EXSTYLE);
    if ((exStyle & WS_EX_TOOLWINDOW) != 0) {
        return false;
    }

    return !getWindowTitle(hwnd).empty();
}

std::vector<WindowInfo> listWindows() {
    std::vector<WindowInfo> windows;
    EnumWindows(enumWindowsProc, reinterpret_cast<LPARAM>(&windows));
    return windows;
}

AppWindowTarget makeAppWindowTarget(
    const std::string& appId,
    const std::string& displayName,
    const std::string& targetPath
) {
    AppWindowTarget target;
    target.appId = appId;
    target.appIdWide = lower(utf8ToWide(appId));
    target.displayName = utf8ToWide(displayName);
    target.targetPath = utf8ToWide(targetPath);
    target.targetFile = filenameOf(target.targetPath);
    return target;
}

bool findAppWindow(
    const std::string& appId,
    const AppWindowTarget& target,
    WindowInfo& out
) {
    auto windows = listWindows();
    bool found = false;

    for (auto& window : windows) {
        window.score = scoreWindow(window, target);
        if (window.score <= 0) {
            continue;
        }

        if (!found || window.score > out.score) {
            out = window;
            found = true;
        }
    }

    if (found) {
        return true;
    }

    const std::wstring appIdWide = lower(utf8ToWide(appId));
    for (auto& window : windows) {
        if (
            containsLower(window.title, appIdWide)
            || containsLower(window.processFile, appIdWide)
        ) {
            window.score = 10;
            out = window;
            return true;
        }
    }

    return false;
}

bool showAndActivateWindow(HWND target) {
    if (target == nullptr || !IsWindow(target)) {
        return false;
    }

    ShowWindow(target, IsIconic(target) ? SW_RESTORE : SW_SHOW);
    return activateWindow(target);
}

nlohmann::json windowToJson(const WindowInfo& window) {
    return {
        {"hwnd", reinterpret_cast<std::uintptr_t>(window.hwnd)},
        {"process_id", window.processId},
        {"title", wideToUtf8(window.title)},
        {"process_path", wideToUtf8(window.processPath)},
        {"process_file", wideToUtf8(window.processFile)},
        {"score", window.score}
    };
}

}
