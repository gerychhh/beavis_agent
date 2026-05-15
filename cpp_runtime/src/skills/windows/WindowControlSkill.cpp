#include "skills/windows/WindowControlSkill.h"

#include <algorithm>
#include <cstdint>
#include <cwctype>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <vector>

#include <windows.h>

#include "resolvers/AppResolver.h"

namespace {
struct WindowInfo {
    HWND hwnd = nullptr;
    DWORD processId = 0;
    std::wstring title;
    std::wstring processPath;
    std::wstring processFile;
    int score = 0;
};

struct TargetInfo {
    std::string appId;
    std::wstring appIdWide;
    std::wstring displayName;
    std::wstring targetPath;
    std::wstring targetFile;
    nlohmann::json resolved = nullptr;
    std::string resolverWarning;
};

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

std::vector<WindowInfo> listWindows() {
    std::vector<WindowInfo> windows;
    EnumWindows(enumWindowsProc, reinterpret_cast<LPARAM>(&windows));
    return windows;
}

bool fillWindowInfo(HWND hwnd, WindowInfo& info) {
    if (!isCandidateWindow(hwnd)) {
        return false;
    }

    DWORD processId = 0;
    GetWindowThreadProcessId(hwnd, &processId);
    if (processId == 0) {
        return false;
    }

    info.hwnd = hwnd;
    info.processId = processId;
    info.title = getWindowTitle(hwnd);
    info.processPath = getProcessPath(processId);
    info.processFile = filenameOf(info.processPath);
    return true;
}

bool isBeavisWindow(const WindowInfo& window) {
    const std::wstring titleLower = lower(window.title);
    const std::wstring fileLower = lower(window.processFile);
    return fileLower.find(L"beavis_desktop_ui") != std::wstring::npos
        || titleLower == L"beavis agent"
        || titleLower == L"beavis command"
        || titleLower == L"beavis voice"
        || titleLower == L"beavis notifications";
}

bool readHwndFromMeta(const nlohmann::json& meta, HWND& hwnd) {
    if (!meta.is_object() || !meta.contains("target_hwnd")) {
        return false;
    }

    try {
        std::uintptr_t raw = 0;
        const auto& value = meta.at("target_hwnd");
        if (value.is_string()) {
            raw = static_cast<std::uintptr_t>(std::stoull(value.get<std::string>()));
        } else if (value.is_number_unsigned()) {
            raw = value.get<std::uintptr_t>();
        } else if (value.is_number_integer()) {
            const auto signedValue = value.get<long long>();
            if (signedValue <= 0) {
                return false;
            }
            raw = static_cast<std::uintptr_t>(signedValue);
        } else {
            return false;
        }

        if (raw == 0) {
            return false;
        }

        hwnd = reinterpret_cast<HWND>(raw);
        return true;
    } catch (...) {
        return false;
    }
}

std::string jsonString(const nlohmann::json& value, const char* key) {
    if (!value.is_object() || !value.contains(key) || !value.at(key).is_string()) {
        return {};
    }

    return value.at(key).get<std::string>();
}

std::string lowerAscii(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        if (ch >= 'A' && ch <= 'Z') {
            return static_cast<char>(ch - 'A' + 'a');
        }
        return static_cast<char>(ch);
    });
    return value;
}

std::string trimAscii(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) {
        return {};
    }

    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

bool startsWithToken(const std::string& value, const std::string& token) {
    if (value == token) {
        return true;
    }
    return value.size() > token.size()
        && value.compare(0, token.size(), token) == 0
        && value[token.size()] == ' ';
}

std::string stripLeadingWakeWord(std::string value) {
    value = trimAscii(value);
    const std::vector<std::string> wakeWords = {
        "beavis",
        "bavis",
        "\xd0\xb1\xd0\xb8\xd0\xb2\xd0\xb8\xd1\x81",
        "\xd0\xb1\xd1\x8b\xd0\xb2\xd0\xb8\xd1\x81",
    };

    for (const std::string& wakeWord : wakeWords) {
        if (startsWithToken(value, wakeWord)) {
            return trimAscii(value.substr(wakeWord.size()));
        }
    }

    return value;
}

bool containsAny(const std::string& value, const std::vector<std::string>& needles) {
    for (const std::string& needle : needles) {
        if (!needle.empty() && value.find(needle) != std::string::npos) {
            return true;
        }
    }

    return false;
}

bool hasExplicitBeavisTarget(const nlohmann::json& meta) {
    std::string rawText = lowerAscii(jsonString(meta, "raw_text"));
    rawText = stripLeadingWakeWord(rawText);

    return containsAny(rawText, {
        "beavis",
        "bavis",
        "beais",
        "bea\xd0\xb2is",
        "dev",
        "\xd0\xb1\xd0\xb8\xd0\xb2\xd0\xb8\xd1\x81",
        "\xd0\xb1\xd1\x8b\xd0\xb2\xd0\xb8\xd1\x81",
    });
}

bool shouldPreferOverlayCurrentForBeavis(
    const std::string& appId,
    const nlohmann::json& meta,
    HWND& hwnd
) {
    if (appId != "beavis_dev" || !readHwndFromMeta(meta, hwnd)) {
        return false;
    }

    return !hasExplicitBeavisTarget(meta);
}

bool containsLower(const std::wstring& value, const std::wstring& needle) {
    if (value.empty() || needle.empty()) {
        return false;
    }

    return lower(value).find(lower(needle)) != std::wstring::npos;
}

TargetInfo makeTargetInfo(const std::string& appId) {
    TargetInfo target;
    target.appId = appId;
    target.appIdWide = lower(utf8ToWide(appId));

    const AppResolver resolver;
    const AppResolveResult resolved = resolver.resolve(appId);
    if (!resolved.ok) {
        target.resolverWarning = resolved.code + ": " + resolved.details;
        return target;
    }

    target.resolved = resolved.target.toJson();
    target.displayName = utf8ToWide(resolved.target.displayName);

    std::string path = resolved.target.targetPath;
    if (path.empty()) {
        path = resolved.target.launchTarget;
    }

    target.targetPath = utf8ToWide(path);
    target.targetFile = filenameOf(target.targetPath);
    return target;
}

int scoreWindow(const WindowInfo& window, const TargetInfo& target) {
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

WindowInfo findAppWindow(const std::string& appId, const TargetInfo& target, bool& found) {
    auto windows = listWindows();
    WindowInfo best;
    found = false;

    for (auto& window : windows) {
        window.score = scoreWindow(window, target);
        if (window.score <= 0) {
            continue;
        }

        if (!found || window.score > best.score) {
            best = window;
            found = true;
        }
    }

    if (!found) {
        const std::wstring appIdWide = lower(utf8ToWide(appId));
        for (auto& window : windows) {
            if (
                containsLower(window.title, appIdWide)
                || containsLower(window.processFile, appIdWide)
            ) {
                window.score = 10;
                best = window;
                found = true;
                break;
            }
        }
    }

    return best;
}

SkillResult failWindowControl(
    const std::string& message,
    const std::string& code,
    const std::string& details
) {
    return SkillResult::fail(nullptr, nullptr, message, code, details);
}

bool applyAction(HWND hwnd, const std::string& action) {
    if (action == "minimize") {
        ShowWindow(hwnd, SW_MINIMIZE);
        return true;
    }

    auto activateWindow = [](HWND target) -> bool {
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
    };

    if (action == "maximize") {
        ShowWindow(hwnd, SW_MAXIMIZE);
        return activateWindow(hwnd);
    }

    if (action == "restore") {
        ShowWindow(hwnd, IsIconic(hwnd) ? SW_RESTORE : SW_SHOW);
        return activateWindow(hwnd);
    }

    if (action == "close") {
        return PostMessageW(hwnd, WM_CLOSE, 0, 0) != 0;
    }

    return false;
}
}

std::string WindowControlSkill::name() const {
    return "window_control";
}

std::string WindowControlSkill::description() const {
    return "Controls visible Windows application windows";
}

std::string WindowControlSkill::riskLevel() const {
    return "medium";
}

SkillResult WindowControlSkill::execute(
    const nlohmann::json& args,
    RuntimeContext& context
) {
    (void)context;

    const std::string action = args.at("action").get<std::string>();
    const std::string targetType = args.at("target_type").get<std::string>();

    WindowInfo window;
    nlohmann::json targetData = nlohmann::json::object();

    if (targetType == "current") {
        HWND hwnd = nullptr;
        if (readHwndFromMeta(context.toolMeta, hwnd) && fillWindowInfo(hwnd, window) && !isBeavisWindow(window)) {
            targetData["source"] = "overlay_target_hwnd";
            targetData["target_hwnd"] = reinterpret_cast<std::uintptr_t>(hwnd);
        } else {
            hwnd = GetForegroundWindow();
            if (!fillWindowInfo(hwnd, window) || isBeavisWindow(window)) {
                return failWindowControl(
                    "No active user window found",
                    "WINDOW_NOT_FOUND",
                    "Foreground window is Beavis, hidden or not controllable"
                );
            }
            targetData["source"] = "foreground";
        }

        if (window.hwnd == nullptr) {
            return failWindowControl(
                "No active window found",
                "WINDOW_NOT_FOUND",
                "Foreground window is empty, hidden or not controllable"
            );
        }
        targetData["target_type"] = "current";
    } else {
        const std::string appId = args.at("app_id").get<std::string>();
        HWND overlayHwnd = nullptr;
        if (
            shouldPreferOverlayCurrentForBeavis(appId, context.toolMeta, overlayHwnd)
            && fillWindowInfo(overlayHwnd, window)
            && !isBeavisWindow(window)
        ) {
            targetData["source"] = "overlay_target_hwnd_guard";
            targetData["target_hwnd"] = reinterpret_cast<std::uintptr_t>(overlayHwnd);
            targetData["target_type"] = "current";
        } else {
            const TargetInfo target = makeTargetInfo(appId);

            bool found = false;
            window = findAppWindow(appId, target, found);
            if (!found) {
                nlohmann::json data = {
                    {"target_type", "app"},
                    {"app_id", appId}
                };
                if (!target.resolverWarning.empty()) {
                    data["resolver_warning"] = target.resolverWarning;
                }

                return failWindowControl(
                    "Window was not found",
                    "WINDOW_NOT_FOUND",
                    "No visible window matched app_id: " + appId
                );
            }

            targetData = {
                {"target_type", "app"},
                {"app_id", appId}
            };
            if (!target.resolved.is_null()) {
                targetData["resolved"] = target.resolved;
            }
            if (!target.resolverWarning.empty()) {
                targetData["resolver_warning"] = target.resolverWarning;
            }
        }
    }

    if (!applyAction(window.hwnd, action)) {
        return failWindowControl(
            "Window action failed",
            "WINDOW_ACTION_FAILED",
            "Failed to apply action: " + action
        );
    }

    return SkillResult::ok(
        "Window action applied: " + action,
        {
            {"action", action},
            {"target", targetData},
            {"window", windowToJson(window)}
        }
    );
}
