#include "skills/apps/OpenAppSkill.h"

#include <cstdint>
#include <string>

#include <windows.h>
#include <shellapi.h>

#include "resolvers/AppResolver.h"
#include "utils/WindowUtils.h"

namespace {
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

SkillResult failOpenApp(
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
}

std::string OpenAppSkill::name() const {
    return "open_app";
}

std::string OpenAppSkill::description() const {
    return "Opens an installed Windows application by app_id";
}

std::string OpenAppSkill::riskLevel() const {
    return "low";
}

SkillResult OpenAppSkill::execute(
    const nlohmann::json& args,
    RuntimeContext& context
) {
    (void)context;

    const std::string appId = args.at("app_id").get<std::string>();
    const AppResolver resolver;
    const AppResolveResult resolved = resolver.resolve(appId);
    if (!resolved.ok) {
        return failOpenApp("Application was not resolved", resolved.code, resolved.details);
    }

    const AppLaunchTarget& target = resolved.target;
    std::string matchPath = target.targetPath;
    if (target.launchType == "apps_folder") {
        matchPath.clear();
    }
    if (matchPath.empty() && target.launchType != "apps_folder") {
        matchPath = target.launchTarget;
    }

    beavis::windows::WindowInfo existingWindow;
    const beavis::windows::AppWindowTarget windowTarget =
        beavis::windows::makeAppWindowTarget(appId, target.displayName, matchPath);

    if (beavis::windows::findAppWindow(appId, windowTarget, existingWindow)) {
        if (!beavis::windows::showAndActivateWindow(existingWindow.hwnd)) {
            return failOpenApp(
                "Application window was found but could not be focused",
                "WINDOW_FOCUS_FAILED",
                "Failed to focus existing window for app_id: " + appId
            );
        }

        return SkillResult::ok(
            "Application focused: " + appId,
            {
                {"app_id", appId},
                {"resolved", target.toJson()},
                {"focused_existing", true},
                {"launched", false},
                {"window", beavis::windows::windowToJson(existingWindow)}
            }
        );
    }

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
        return failOpenApp(
            "Failed to open application",
            shellExecuteErrorCode(code),
            "ShellExecuteW failed for app_id: " + appId + ", target: " + target.launchTarget
        );
    }

    return SkillResult::ok(
        "Application opened: " + appId,
        {
            {"app_id", appId},
            {"resolved", target.toJson()},
            {"focused_existing", false},
            {"launched", true}
        }
    );
}
