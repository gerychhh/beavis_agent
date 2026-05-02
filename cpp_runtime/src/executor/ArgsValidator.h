#pragma once

#include <string>

#include "core/ToolCall.h"

struct ValidationResult {
    bool ok = true;
    std::string code;
    std::string details;

    static ValidationResult valid();
    static ValidationResult invalid(
        const std::string& code,
        const std::string& details
    );
};

class ArgsValidator {
public:
    ValidationResult validate(const ToolCall& call) const;

private:
    ValidationResult validateVolumeSet(const ToolCall& call) const;
    ValidationResult validateOpenApp(const ToolCall& call) const;
    ValidationResult validateWindowControl(const ToolCall& call) const;
    ValidationResult validateWindowLayout(const ToolCall& call) const;
    ValidationResult validateWindowSnap(const ToolCall& call) const;
};
