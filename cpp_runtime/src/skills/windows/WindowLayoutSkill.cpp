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

bool findCurrentWindow(beavis::windows::WindowInfo& out) {
    HWND foreground = GetForegroundWindow();
    if (foreground == nullptr || !beavis::windows::isCandidateWindow(foreground)) {
        return false;
    }

    for (const auto& window : beavis::windows::listWindows()) {
        if (window.hwnd == foreground) {
            out = window;
            return true;
        }
    }

    out.hwnd = foreground;
    return true;
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
    TargetWindow& out
) {
    if (appId == "current") {
        if (!findCurrentWindow(out.window)) {
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
}

std::string WindowLayoutSkill::name() const {
    return "window_layout";
}

std::string WindowLayoutSkill::description() const {
    return "Arranges existing windows on the screen";
}

std::string WindowLayoutSkill::riskLevel() const {
    return "medium";
}

SkillResult WindowLayoutSkill::execute(
    const nlohmann::json& args,
    RuntimeContext& context
) {
    (void)context;

    const std::string layout = args.at("layout").get<std::string>();
    const std::vector<std::string> targets = args.at("targets").get<std::vector<std::string>>();
    const std::vector<Placement> placements = placementsFor(layout, targets.size());
    if (placements.empty()) {
        return failWindowLayout("Unsupported window layout", "UNSUPPORTED_LAYOUT", "layout: " + layout);
    }

    const size_t windowCount = std::min(targets.size(), placements.size());
    std::vector<TargetWindow> targetWindows;
    targetWindows.reserve(windowCount);

    for (size_t index = 0; index < windowCount; ++index) {
        TargetWindow targetWindow;
        SkillResult lookupResult = findOrLaunchTargetWindow(targets[index], targetWindow);
        if (!lookupResult.success) {
            return lookupResult;
        }
        targetWindows.push_back(targetWindow);
    }

    nlohmann::json moved = nlohmann::json::array();
    for (size_t index = 0; index < targetWindows.size(); ++index) {
        const Placement& placement = placements[index];
        if (!applyPlacement(targetWindows[index].window.hwnd, placement)) {
            return failWindowLayout(
                "Window could not be moved",
                "WINDOW_MOVE_FAILED",
                "SetWindowPos failed for target: " + targets[index]
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
