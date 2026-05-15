#include "skills/windows/WindowLayoutSkill.h"

#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>

#include <windows.h>
#include <shellapi.h>

#include "resolvers/AppResolver.h"
#include "utils/WindowUtils.h"

namespace {
constexpr DWORD kActivationDelayMs = 120;
constexpr DWORD kSnapDelayMs = 240;
constexpr LONG kPlacementTolerancePx = 96;

struct Placement {
    LONG x = 0;
    LONG y = 0;
    LONG width = 0;
    LONG height = 0;
};

struct TargetWindow {
    beavis::windows::WindowInfo window;
    nlohmann::json resolved = nullptr;
    bool launched = false;
};

struct SnapCommand {
    WORD arrowKey = 0;
    bool useAlt = false;
    bool verifyPlacement = false;
};

struct ApplyResult {
    bool success = false;
    std::string method;
};

std::string shellExecuteErrorCode(INT_PTR code) {
    switch (code) {
        case 0:
            return "OUT_OF_MEMORY";
        case ERROR_FILE_NOT_FOUND:
            return "FILE_NOT_FOUND";
        case ERROR_PATH_NOT_FOUND:
            return "PATH_NOT_FOUND";
        case ERROR_BAD_FORMAT:
            return "BAD_FORMAT";
        case SE_ERR_ACCESSDENIED:
            return "ACCESS_DENIED";
        case SE_ERR_ASSOCINCOMPLETE:
            return "ASSOC_INCOMPLETE";
        case SE_ERR_DDEBUSY:
            return "DDE_BUSY";
        case SE_ERR_DDEFAIL:
            return "DDE_FAIL";
        case SE_ERR_DDETIMEOUT:
            return "DDE_TIMEOUT";
        case SE_ERR_DLLNOTFOUND:
            return "DLL_NOT_FOUND";
        case SE_ERR_NOASSOC:
            return "NO_ASSOC";
        case SE_ERR_OOM:
            return "OUT_OF_MEMORY";
        case SE_ERR_SHARE:
            return "SHARE_ERROR";
        default:
            return "SHELL_EXECUTE_FAILED";
    }
}

SkillResult failWindowLayout(
    const std::string& message,
    const std::string& code,
    const std::string& details
) {
    return SkillResult::fail(
        nullptr,
        nullptr,
        message,
        code,
        details
    );
}

std::string matchPathFor(const AppLaunchTarget& target) {
    if (target.launchType == "apps_folder") {
        return "";
    }

    if (!target.targetPath.empty()) {
        return target.targetPath;
    }

    return target.launchTarget;
}

RECT workArea() {
    RECT rect{};
    if (!SystemParametersInfoW(SPI_GETWORKAREA, 0, &rect, 0)) {
        rect.left = 0;
        rect.top = 0;
        rect.right = GetSystemMetrics(SM_CXSCREEN);
        rect.bottom = GetSystemMetrics(SM_CYSCREEN);
    }

    return rect;
}

Placement makePlacement(const RECT& area, double x, double y, double width, double height) {
    const LONG areaWidth = area.right - area.left;
    const LONG areaHeight = area.bottom - area.top;

    return {
        area.left + static_cast<LONG>(areaWidth * x),
        area.top + static_cast<LONG>(areaHeight * y),
        static_cast<LONG>(areaWidth * width),
        static_cast<LONG>(areaHeight * height),
    };
}

std::vector<Placement> placementsFor(const std::string& layout, size_t count) {
    const RECT area = workArea();

    if (layout == "left_half") {
        return {makePlacement(area, 0.0, 0.0, 0.5, 1.0)};
    }
    if (layout == "right_half") {
        return {makePlacement(area, 0.5, 0.0, 0.5, 1.0)};
    }
    if (layout == "top_half") {
        return {makePlacement(area, 0.0, 0.0, 1.0, 0.5)};
    }
    if (layout == "bottom_half") {
        return {makePlacement(area, 0.0, 0.5, 1.0, 0.5)};
    }
    if (layout == "center") {
        return {makePlacement(area, 0.15, 0.12, 0.70, 0.76)};
    }
    if (layout == "fullscreen") {
        return {makePlacement(area, 0.0, 0.0, 1.0, 1.0)};
    }
    if (layout == "split_2_vertical") {
        return {
            makePlacement(area, 0.0, 0.0, 0.5, 1.0),
            makePlacement(area, 0.5, 0.0, 0.5, 1.0),
        };
    }
    if (layout == "split_2_horizontal") {
        return {
            makePlacement(area, 0.0, 0.0, 1.0, 0.5),
            makePlacement(area, 0.0, 0.5, 1.0, 0.5),
        };
    }
    if (layout == "grid_2x2") {
        return {
            makePlacement(area, 0.0, 0.0, 0.5, 0.5),
            makePlacement(area, 0.5, 0.0, 0.5, 0.5),
            makePlacement(area, 0.0, 0.5, 0.5, 0.5),
            makePlacement(area, 0.5, 0.5, 0.5, 0.5),
        };
    }

    (void)count;
    return {};
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

bool isBeavisWindow(const beavis::windows::WindowInfo& window) {
    const std::wstring titleLower = beavis::windows::lower(window.title);
    const std::wstring fileLower = beavis::windows::lower(window.processFile);
    return fileLower.find(L"beavis_desktop_ui") != std::wstring::npos
        || titleLower == L"beavis agent"
        || titleLower == L"beavis command"
        || titleLower == L"beavis voice"
        || titleLower == L"beavis notifications";
}

bool findWindowByHwnd(HWND hwnd, beavis::windows::WindowInfo& out) {
    if (hwnd == nullptr || !beavis::windows::isCandidateWindow(hwnd)) {
        return false;
    }

    for (const auto& window : beavis::windows::listWindows()) {
        if (window.hwnd == hwnd) {
            out = window;
            return !isBeavisWindow(out);
        }
    }

    return false;
}

bool findCurrentWindow(const nlohmann::json& meta, beavis::windows::WindowInfo& out) {
    HWND metaHwnd = nullptr;
    if (readHwndFromMeta(meta, metaHwnd) && findWindowByHwnd(metaHwnd, out)) {
        return true;
    }

    HWND foreground = GetForegroundWindow();
    return findWindowByHwnd(foreground, out);
}

bool launchTarget(
    const std::string& appId,
    const AppLaunchTarget& target,
    std::string& errorCode,
    std::string& details
) {
    const std::wstring operation = L"open";
    const std::wstring file = beavis::windows::utf8ToWide(target.launchTarget);
    const std::wstring parameters = beavis::windows::utf8ToWide(target.arguments);
    const std::wstring directory = beavis::windows::utf8ToWide(target.workingDirectory);

    HINSTANCE result = ShellExecuteW(
        nullptr,
        operation.c_str(),
        file.c_str(),
        parameters.empty() ? nullptr : parameters.c_str(),
        directory.empty() ? nullptr : directory.c_str(),
        SW_SHOWNORMAL
    );

    const INT_PTR code = reinterpret_cast<INT_PTR>(result);
    if (code <= 32) {
        errorCode = shellExecuteErrorCode(code);
        details = "ShellExecuteW failed for app_id: " + appId + ", target: " + target.launchTarget;
        return false;
    }

    return true;
}

bool waitForTargetWindow(
    const std::string& appId,
    const beavis::windows::AppWindowTarget& windowTarget,
    beavis::windows::WindowInfo& out,
    DWORD timeoutMs = 12000,
    DWORD intervalMs = 250
) {
    const ULONGLONG startedAt = GetTickCount64();
    while (GetTickCount64() - startedAt <= timeoutMs) {
        if (beavis::windows::findAppWindow(appId, windowTarget, out)) {
            return true;
        }
        Sleep(intervalMs);
    }

    return false;
}

SkillResult findOrLaunchTargetWindow(
    const std::string& appId,
    const nlohmann::json& meta,
    TargetWindow& out
) {
    if (appId == "current") {
        if (!findCurrentWindow(meta, out.window)) {
            return failWindowLayout(
                "Window was not found",
                "WINDOW_NOT_FOUND",
                "No active window was found for target: current"
            );
        }
        return SkillResult::ok("Window found", {});
    }

    const AppResolver resolver;
    const AppResolveResult resolved = resolver.resolve(appId);
    if (!resolved.ok) {
        return failWindowLayout(
            "Application was not resolved",
            resolved.code,
            resolved.details
        );
    }

    const AppLaunchTarget& target = resolved.target;
    out.resolved = target.toJson();

    const beavis::windows::AppWindowTarget windowTarget =
        beavis::windows::makeAppWindowTarget(appId, target.displayName, matchPathFor(target));

    if (beavis::windows::findAppWindow(appId, windowTarget, out.window)) {
        return SkillResult::ok("Window found", {});
    }

    std::string errorCode;
    std::string details;
    if (!launchTarget(appId, target, errorCode, details)) {
        return failWindowLayout(
            "Failed to open application for window layout",
            errorCode,
            details
        );
    }

    out.launched = true;
    if (!waitForTargetWindow(appId, windowTarget, out.window)) {
        return failWindowLayout(
            "Window was not found after launching application",
            "WINDOW_NOT_FOUND_AFTER_LAUNCH",
            "No visible window appeared for target: " + appId
        );
    }

    return SkillResult::ok("Window found", {});
}

bool applyPlacement(HWND hwnd, const Placement& placement) {
    if (hwnd == nullptr || !IsWindow(hwnd)) {
        return false;
    }

    ShowWindow(hwnd, SW_RESTORE);
    return SetWindowPos(
        hwnd,
        HWND_TOP,
        placement.x,
        placement.y,
        placement.width,
        placement.height,
        SWP_SHOWWINDOW
    ) != 0;
}

HWND rootOf(HWND hwnd) {
    if (hwnd == nullptr || !IsWindow(hwnd)) {
        return nullptr;
    }

    HWND root = GetAncestor(hwnd, GA_ROOT);
    return root != nullptr ? root : hwnd;
}

bool isForegroundTarget(HWND hwnd) {
    HWND foreground = GetForegroundWindow();
    if (foreground == nullptr || hwnd == nullptr) {
        return false;
    }

    return foreground == hwnd || rootOf(foreground) == rootOf(hwnd);
}

bool activateWindowForInput(HWND hwnd) {
    if (hwnd == nullptr || !IsWindow(hwnd)) {
        return false;
    }

    if (IsIconic(hwnd) || IsZoomed(hwnd)) {
        ShowWindow(hwnd, SW_RESTORE);
    } else {
        ShowWindow(hwnd, SW_SHOW);
    }

    beavis::windows::showAndActivateWindow(hwnd);
    Sleep(kActivationDelayMs);
    if (isForegroundTarget(hwnd)) {
        return true;
    }

    BringWindowToTop(hwnd);
    SetForegroundWindow(hwnd);
    Sleep(kActivationDelayMs);
    return isForegroundTarget(hwnd);
}

bool isExtendedKey(WORD key) {
    switch (key) {
        case VK_LEFT:
        case VK_RIGHT:
        case VK_UP:
        case VK_DOWN:
        case VK_HOME:
        case VK_END:
        case VK_PRIOR:
        case VK_NEXT:
        case VK_INSERT:
        case VK_DELETE:
        case VK_LWIN:
        case VK_RWIN:
            return true;
        default:
            return false;
    }
}

void pushKeyInput(std::vector<INPUT>& inputs, WORD key, bool down) {
    INPUT input{};
    input.type = INPUT_KEYBOARD;
    input.ki.wVk = key;
    input.ki.dwFlags = isExtendedKey(key) ? KEYEVENTF_EXTENDEDKEY : 0;
    if (!down) {
        input.ki.dwFlags |= KEYEVENTF_KEYUP;
    }

    inputs.push_back(input);
}

bool sendWinArrow(WORD arrowKey, bool useAlt) {
    std::vector<INPUT> inputs;
    inputs.reserve(useAlt ? 6 : 4);

    pushKeyInput(inputs, VK_LWIN, true);
    if (useAlt) {
        pushKeyInput(inputs, VK_MENU, true);
    }
    pushKeyInput(inputs, arrowKey, true);
    pushKeyInput(inputs, arrowKey, false);
    if (useAlt) {
        pushKeyInput(inputs, VK_MENU, false);
    }
    pushKeyInput(inputs, VK_LWIN, false);

    const UINT sent = SendInput(
        static_cast<UINT>(inputs.size()),
        inputs.data(),
        static_cast<int>(sizeof(INPUT))
    );

    Sleep(kSnapDelayMs);
    return sent == static_cast<UINT>(inputs.size());
}

LONG absLong(LONG value) {
    return value < 0 ? -value : value;
}

bool closeTo(LONG actual, LONG expected, LONG tolerance) {
    return absLong(actual - expected) <= tolerance;
}

bool placementLooksClose(HWND hwnd, const Placement& expected) {
    RECT actual{};
    if (hwnd == nullptr || !IsWindow(hwnd) || !GetWindowRect(hwnd, &actual)) {
        return false;
    }

    const LONG actualWidth = actual.right - actual.left;
    const LONG actualHeight = actual.bottom - actual.top;

    return closeTo(actual.left, expected.x, kPlacementTolerancePx)
        && closeTo(actual.top, expected.y, kPlacementTolerancePx)
        && closeTo(actualWidth, expected.width, kPlacementTolerancePx * 2)
        && closeTo(actualHeight, expected.height, kPlacementTolerancePx * 2);
}

std::vector<SnapCommand> nativeSnapSequenceFor(const std::string& layout, size_t index) {
    if (layout == "left_half" && index == 0) {
        return {{VK_LEFT, false, false}};
    }
    if (layout == "right_half" && index == 0) {
        return {{VK_RIGHT, false, false}};
    }

    // Windows 11 supports Win+Alt+Up/Down for top/bottom snap.
    // On older systems it may do nothing, so these commands are verified and can fall back to SetWindowPos.
    if (layout == "top_half" && index == 0) {
        return {{VK_UP, true, true}};
    }
    if (layout == "bottom_half" && index == 0) {
        return {{VK_DOWN, true, true}};
    }

    if (layout == "split_2_vertical") {
        if (index == 0) {
            return {{VK_LEFT, false, false}};
        }
        if (index == 1) {
            return {{VK_RIGHT, false, false}};
        }
    }

    if (layout == "split_2_horizontal") {
        if (index == 0) {
            return {{VK_UP, true, true}};
        }
        if (index == 1) {
            return {{VK_DOWN, true, true}};
        }
    }

    if (layout == "grid_2x2") {
        if (index == 0) {
            return {{VK_LEFT, false, false}, {VK_UP, false, false}};
        }
        if (index == 1) {
            return {{VK_RIGHT, false, false}, {VK_UP, false, false}};
        }
        if (index == 2) {
            return {{VK_LEFT, false, false}, {VK_DOWN, false, false}};
        }
        if (index == 3) {
            return {{VK_RIGHT, false, false}, {VK_DOWN, false, false}};
        }
    }

    return {};
}

bool sequenceNeedsVerification(const std::vector<SnapCommand>& sequence) {
    for (const SnapCommand& command : sequence) {
        if (command.verifyPlacement) {
            return true;
        }
    }

    return false;
}

bool applyNativeSnap(HWND hwnd, const std::vector<SnapCommand>& sequence, const Placement& expected) {
    if (sequence.empty()) {
        return false;
    }

    if (!activateWindowForInput(hwnd)) {
        return false;
    }

    for (const SnapCommand& command : sequence) {
        if (!isForegroundTarget(hwnd)) {
            return false;
        }
        if (!sendWinArrow(command.arrowKey, command.useAlt)) {
            return false;
        }
    }

    if (sequenceNeedsVerification(sequence) && !placementLooksClose(hwnd, expected)) {
        return false;
    }

    return true;
}

bool applyMaximized(HWND hwnd) {
    if (hwnd == nullptr || !IsWindow(hwnd)) {
        return false;
    }

    if (IsIconic(hwnd)) {
        ShowWindow(hwnd, SW_RESTORE);
        Sleep(kActivationDelayMs);
    }

    beavis::windows::showAndActivateWindow(hwnd);
    Sleep(kActivationDelayMs);
    ShowWindow(hwnd, SW_MAXIMIZE);
    Sleep(kActivationDelayMs);

    return IsWindow(hwnd) && IsWindowVisible(hwnd);
}

ApplyResult applyLayoutToWindow(
    HWND hwnd,
    const std::string& layout,
    size_t index,
    const Placement& placement
) {
    if (layout == "fullscreen") {
        if (applyMaximized(hwnd)) {
            return {true, "native_maximize"};
        }
        if (applyPlacement(hwnd, placement)) {
            return {true, "set_window_pos_fallback"};
        }
        return {false, "native_maximize_and_fallback_failed"};
    }

    const std::vector<SnapCommand> sequence = nativeSnapSequenceFor(layout, index);
    if (!sequence.empty()) {
        if (applyNativeSnap(hwnd, sequence, placement)) {
            return {true, "native_snap"};
        }
        if (applyPlacement(hwnd, placement)) {
            return {true, "set_window_pos_fallback"};
        }
        return {false, "native_snap_and_fallback_failed"};
    }

    if (applyPlacement(hwnd, placement)) {
        return {true, "set_window_pos"};
    }

    return {false, "set_window_pos_failed"};
}

bool readArgs(
    const nlohmann::json& args,
    std::string& layout,
    std::vector<std::string>& targets,
    std::string& details
) {
    if (!args.contains("layout") || !args.at("layout").is_string()) {
        details = "Argument 'layout' must be a string";
        return false;
    }
    if (!args.contains("targets") || !args.at("targets").is_array()) {
        details = "Argument 'targets' must be an array of strings";
        return false;
    }

    layout = args.at("layout").get<std::string>();
    targets.clear();

    for (const auto& item : args.at("targets")) {
        if (!item.is_string()) {
            details = "Every item in 'targets' must be a string";
            return false;
        }
        targets.push_back(item.get<std::string>());
    }

    if (targets.empty()) {
        details = "Argument 'targets' must contain at least one target";
        return false;
    }

    return true;
}
}

std::string WindowLayoutSkill::name() const {
    return "window_layout";
}

std::string WindowLayoutSkill::description() const {
    return "Arranges visible Windows application windows using native Snap when possible";
}

std::string WindowLayoutSkill::riskLevel() const {
    return "medium";
}

SkillResult WindowLayoutSkill::execute(
    const nlohmann::json& args,
    RuntimeContext& context
) {
    std::string layout;
    std::vector<std::string> targets;
    std::string details;
    if (!readArgs(args, layout, targets, details)) {
        return failWindowLayout(
            "Invalid window layout arguments",
            "INVALID_ARGUMENTS",
            details
        );
    }

    const std::vector<Placement> placements = placementsFor(layout, targets.size());
    if (placements.empty()) {
        return failWindowLayout(
            "Unsupported window layout",
            "UNSUPPORTED_LAYOUT",
            "layout: " + layout
        );
    }

    const size_t windowCount = std::min(targets.size(), placements.size());
    std::vector<TargetWindow> targetWindows;
    targetWindows.reserve(windowCount);

    for (size_t index = 0; index < windowCount; ++index) {
        TargetWindow targetWindow;
        SkillResult lookupResult = findOrLaunchTargetWindow(
            targets[index],
            context.toolMeta,
            targetWindow
        );
        if (!lookupResult.success) {
            return lookupResult;
        }
        targetWindows.push_back(targetWindow);
    }

    nlohmann::json moved = nlohmann::json::array();
    for (size_t index = 0; index < targetWindows.size(); ++index) {
        const Placement& placement = placements[index];
        const ApplyResult applyResult = applyLayoutToWindow(
            targetWindows[index].window.hwnd,
            layout,
            index,
            placement
        );

        if (!applyResult.success) {
            return failWindowLayout(
                "Window could not be moved",
                "WINDOW_MOVE_FAILED",
                "Failed to apply layout for target: " + targets[index] + ", method: " + applyResult.method
            );
        }

        moved.push_back({
            {"target", targets[index]},
            {"placement", {
                {"x", placement.x},
                {"y", placement.y},
                {"width", placement.width},
                {"height", placement.height}
            }},
            {"method", applyResult.method},
            {"window", beavis::windows::windowToJson(targetWindows[index].window)},
            {"launched", targetWindows[index].launched},
            {"resolved", targetWindows[index].resolved}
        });
    }

    if (!targetWindows.empty()) {
        beavis::windows::showAndActivateWindow(targetWindows.back().window.hwnd);
    }

    return SkillResult::ok(
        "Window layout applied: " + layout,
        {
            {"layout", layout},
            {"targets", targets},
            {"moved", moved}
        }
    );
}
