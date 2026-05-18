#pragma once

#include "skills/ISkill.h"

class WebSearchSkill : public ISkill {
public:
    std::string name() const override;
    std::string description() const override;
    std::string riskLevel() const override;

    SkillResult execute(
        const nlohmann::json& args,
        RuntimeContext& context
    ) override;
};
