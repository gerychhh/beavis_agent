#include "executor/Executor.h"

#include <exception>
#include <stdexcept>
#include <string>

Executor::Executor(SkillRegistry& registry)
    : registry_(registry) {
}

SkillResult Executor::execute(const nlohmann::json& input) {
    const nlohmann::json requestId = getRequestId(input);
    const nlohmann::json skillName = getSkill(input);

    ToolCall call;
    try {
        call = parseToolCall(input);
    } catch (const std::invalid_argument& error) {
        return SkillResult::fail(
            requestId,
            skillName,
            "Invalid ToolCall",
            "INVALID_ARGS",
            error.what()
        );
    }

    if (call.type != "tool_call") {
        return SkillResult::fail(
            call.requestId,
            call.skill,
            "Invalid message type",
            "INVALID_TYPE",
            "Expected type: tool_call"
        );
    }

    ISkill* skill = registry_.find(call.skill);
    if (skill == nullptr) {
        return SkillResult::fail(
            call.requestId,
            call.skill,
            "Unknown skill",
            "UNKNOWN_SKILL",
            "Skill is not registered"
        );
    }

    const ValidationResult validation = validator_.validate(call);
    if (!validation.ok) {
        return SkillResult::fail(
            call.requestId,
            call.skill,
            "Invalid skill arguments",
            validation.code,
            validation.details
        );
    }

    try {
        SkillResult result = skill->execute(call.args, context_);
        result.requestId = call.requestId;
        result.skill = call.skill;
        return result;
    } catch (const std::exception& error) {
        return SkillResult::fail(
            call.requestId,
            call.skill,
            "Skill failed",
            "SKILL_FAILED",
            error.what()
        );
    }
}

ToolCall Executor::parseToolCall(const nlohmann::json& input) const {
    if (!input.is_object()) {
        throw std::invalid_argument("ToolCall must be a JSON object");
    }

    if (!input.contains("request_id") || !input.at("request_id").is_string()) {
        throw std::invalid_argument("request_id is required and must be a string");
    }

    if (!input.contains("type") || !input.at("type").is_string()) {
        throw std::invalid_argument("type is required and must be a string");
    }

    if (!input.contains("skill") || !input.at("skill").is_string()) {
        throw std::invalid_argument("skill is required and must be a string");
    }

    if (!input.contains("args") || !input.at("args").is_object()) {
        throw std::invalid_argument("args is required and must be an object");
    }

    ToolCall call;
    call.requestId = input.at("request_id").get<std::string>();
    call.type = input.at("type").get<std::string>();
    call.skill = input.at("skill").get<std::string>();
    call.args = input.at("args");

    if (input.contains("meta")) {
        call.meta = input.at("meta");
    }

    return call;
}

nlohmann::json Executor::getRequestId(const nlohmann::json& input) const {
    if (input.is_object() && input.contains("request_id") && input.at("request_id").is_string()) {
        return input.at("request_id");
    }

    return nullptr;
}

nlohmann::json Executor::getSkill(const nlohmann::json& input) const {
    if (input.is_object() && input.contains("skill") && input.at("skill").is_string()) {
        return input.at("skill");
    }

    return nullptr;
}
