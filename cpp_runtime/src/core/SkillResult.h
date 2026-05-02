#pragma once

#include <string>

#include <nlohmann/json.hpp>

struct SkillResult {
    nlohmann::json requestId = nullptr;
    nlohmann::json skill = nullptr;
    bool success = false;
    std::string message;
    nlohmann::json data = nlohmann::json::object();
    nlohmann::json error = nullptr;

    static SkillResult ok(
        const std::string& message,
        const nlohmann::json& data = nlohmann::json::object()
    ) {
        SkillResult result;
        result.success = true;
        result.message = message;
        result.data = data;
        result.error = nullptr;
        return result;
    }

    static SkillResult fail(
        const nlohmann::json& requestId,
        const nlohmann::json& skill,
        const std::string& message,
        const std::string& code,
        const std::string& details
    ) {
        SkillResult result;
        result.requestId = requestId;
        result.skill = skill;
        result.success = false;
        result.message = message;
        result.data = nlohmann::json::object();
        result.error = {
            {"code", code},
            {"details", details}
        };
        return result;
    }

    nlohmann::json toJson() const {
        return {
            {"request_id", requestId},
            {"type", "skill_result"},
            {"success", success},
            {"skill", skill},
            {"message", message},
            {"data", data},
            {"error", error}
        };
    }
};
