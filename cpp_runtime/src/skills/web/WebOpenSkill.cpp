#include "skills/web/WebOpenSkill.h"

#include <cstdint>
#include <string>

#include <windows.h>
#include <shellapi.h>

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
}

std::string WebOpenSkill::name() const {
    return "web_open";
}

std::string WebOpenSkill::description() const {
    return "Opens a web URL in the default browser";
}

std::string WebOpenSkill::riskLevel() const {
    return "low";
}

SkillResult WebOpenSkill::execute(
    const nlohmann::json& args,
    RuntimeContext& context
) {
    (void)context;

    const std::string url = args.at("url").get<std::string>();
    const std::wstring operation = L"open";
    const std::wstring file = beavis::windows::utf8ToWide(url);

    HINSTANCE result = ShellExecuteW(
        nullptr,
        operation.c_str(),
        file.c_str(),
        nullptr,
        nullptr,
        SW_SHOWNORMAL
    );

    const INT_PTR code = reinterpret_cast<INT_PTR>(result);
    if (code <= 32) {
        return SkillResult::fail(
            nullptr,
            nullptr,
            "Failed to open URL",
            shellExecuteErrorCode(code),
            "ShellExecuteW failed for URL: " + url
        );
    }

    nlohmann::json data = {
        {"url", url},
        {"action", args.value("action", "")},
        {"site_id", args.value("site_id", "")}
    };

    return SkillResult::ok("Opened URL: " + url, data);
}
