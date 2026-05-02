#include "executor/SkillRegistry.h"

#include <stdexcept>

void SkillRegistry::registerSkill(std::unique_ptr<ISkill> skill) {
    if (!skill) {
        throw std::invalid_argument("Cannot register null skill");
    }

    const std::string skillName = skill->name();
    skills_[skillName] = std::move(skill);
}

ISkill* SkillRegistry::find(const std::string& name) const {
    const auto it = skills_.find(name);
    if (it == skills_.end()) {
        return nullptr;
    }

    return it->second.get();
}
