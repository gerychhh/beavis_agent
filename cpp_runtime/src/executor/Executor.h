#pragma once

#include <string>

#include <nlohmann/json.hpp>

#include "core/RuntimeContext.h"
#include "core/SkillResult.h"
#include "core/ToolCall.h"
#include "executor/ArgsValidator.h"
#include "executor/SkillRegistry.h"

class Executor {
public:
    explicit Executor(SkillRegistry& registry);

    SkillResult execute(const nlohmann::json& input);

private:
    SkillRegistry& registry_;
    ArgsValidator validator_;
    RuntimeContext context_;

    ToolCall parseToolCall(const nlohmann::json& input) const;
    nlohmann::json getRequestId(const nlohmann::json& input) const;
    nlohmann::json getSkill(const nlohmann::json& input) const;
};
