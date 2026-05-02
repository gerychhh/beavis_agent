#pragma once

#include <string>

#include <nlohmann/json.hpp>

#include "core/RuntimeContext.h"
#include "core/SkillResult.h"
#include "skills/ISkill.h"

class WindowControlSkill : public ISkill {
public:
    std::string name() const override;
    std::string description() const override;
    std::string riskLevel() const override;

    SkillResult execute(
        const nlohmann::json& args,
        RuntimeContext& context
    ) override;
};

