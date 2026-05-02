#pragma once

#include <string>

#include <nlohmann/json.hpp>

#include "core/RuntimeContext.h"
#include "core/SkillResult.h"

class ISkill {
public:
    virtual ~ISkill() = default;

    virtual std::string name() const = 0;
    virtual std::string description() const = 0;
    virtual std::string riskLevel() const = 0;

    virtual SkillResult execute(
        const nlohmann::json& args,
        RuntimeContext& context
    ) = 0;
};
