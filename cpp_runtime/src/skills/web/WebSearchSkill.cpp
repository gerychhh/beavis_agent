#include "skills/web/WebSearchSkill.h"

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

std::string WebSearchSkill::name() const {
    return "web_search";
}

std::string WebSearchSkill::description() const {
    return "Opens a Google search URL in the default browser";
}

std::string WebSearchSkill::riskLevel() const {
    return "low";
}

SkillResult WebSearchSkill::execute(
    const nlohmann::json& args,
    RuntimeContext& context
) {
    (void)context;

    const std::string url = args.at("url").get<std::string>();
    const std::string query = args.at("query").get<std::string>();
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
            "Failed to open search URL",
            shellExecuteErrorCode(code),
            "ShellExecuteW failed for URL: " + url
        );
    }

    nlohmann::json data = {
        {"url", url},
        {"query", query},
        {"action", args.value("action", "")},
        {"provider", args.value("provider", "")}
    };

    return SkillResult::ok("Opened web search: " + query, data);
}
