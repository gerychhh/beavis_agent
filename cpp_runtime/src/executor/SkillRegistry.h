#pragma once

#include <memory>
#include <string>
#include <unordered_map>

#include "skills/ISkill.h"

class SkillRegistry {
public:
    void registerSkill(std::unique_ptr<ISkill> skill);
    ISkill* find(const std::string& name) const;

private:
    std::unordered_map<std::string, std::unique_ptr<ISkill>> skills_;
};
