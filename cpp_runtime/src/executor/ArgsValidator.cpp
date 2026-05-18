#include "executor/ArgsValidator.h"

#include <string>
#include <unordered_set>

ValidationResult ValidationResult::valid() {
    return {};
}

ValidationResult ValidationResult::invalid(
    const std::string& code,
    const std::string& details
) {
    ValidationResult result;
    result.ok = false;
    result.code = code;
    result.details = details;
    return result;
}

ValidationResult ArgsValidator::validate(const ToolCall& call) const {
    if (call.skill == "volume_set") {
        return validateVolumeSet(call);
    }

    if (call.skill == "open_app") {
        return validateOpenApp(call);
    }

    if (call.skill == "web_open") {
        return validateWebOpen(call);
    }

    if (call.skill == "web_search") {
        return validateWebSearch(call);
    }

    if (call.skill == "window_control") {
        return validateWindowControl(call);
    }

    if (call.skill == "window_layout") {
        return validateWindowLayout(call);
    }

    if (call.skill == "window_snap") {
        return validateWindowSnap(call);
    }

    return ValidationResult::valid();
}

ValidationResult ArgsValidator::validateVolumeSet(const ToolCall& call) const {
    if (!call.args.contains("mode")) {
        if (call.args.contains("percent")) {
            if (!call.args.at("percent").is_number_integer()) {
                return ValidationResult::invalid("INVALID_ARGS", "percent must be an integer");
            }

            const int percent = call.args.at("percent").get<int>();
            if (percent < 0 || percent > 100) {
                return ValidationResult::invalid("INVALID_ARGS", "percent must be between 0 and 100");
            }

            return ValidationResult::valid();
        }

        return ValidationResult::invalid("MISSING_ARG", "Missing required arg: mode");
    }

    if (!call.args.at("mode").is_string()) {
        return ValidationResult::invalid("INVALID_ARGS", "mode must be a string");
    }

    const std::string mode = call.args.at("mode").get<std::string>();
    if (mode == "set") {
        if (!call.args.contains("percent")) {
            return ValidationResult::invalid("MISSING_ARG", "Missing required arg: percent");
        }

        if (!call.args.at("percent").is_number_integer()) {
            return ValidationResult::invalid("INVALID_ARGS", "percent must be an integer");
        }

        const int percent = call.args.at("percent").get<int>();
        if (percent < 0 || percent > 100) {
            return ValidationResult::invalid("INVALID_ARGS", "percent must be between 0 and 100");
        }

        return ValidationResult::valid();
    }

    if (mode == "delta") {
        if (!call.args.contains("delta")) {
            return ValidationResult::invalid("MISSING_ARG", "Missing required arg: delta");
        }

        if (!call.args.at("delta").is_number_integer()) {
            return ValidationResult::invalid("INVALID_ARGS", "delta must be an integer");
        }

        const int delta = call.args.at("delta").get<int>();
        if (delta < -100 || delta > 100) {
            return ValidationResult::invalid("INVALID_ARGS", "delta must be between -100 and 100");
        }

        return ValidationResult::valid();
    }

    return ValidationResult::invalid("INVALID_ARGS", "mode must be set or delta");
}

ValidationResult ArgsValidator::validateOpenApp(const ToolCall& call) const {
    if (!call.args.contains("app_id")) {
        return ValidationResult::invalid("MISSING_ARG", "Missing required arg: app_id");
    }

    if (!call.args.at("app_id").is_string() || call.args.at("app_id").get<std::string>().empty()) {
        return ValidationResult::invalid("INVALID_ARGS", "app_id must be a non-empty string");
    }

    return ValidationResult::valid();
}

ValidationResult ArgsValidator::validateWebOpen(const ToolCall& call) const {
    if (!call.args.contains("url")) {
        return ValidationResult::invalid("MISSING_ARG", "Missing required arg: url");
    }

    if (!call.args.at("url").is_string() || call.args.at("url").get<std::string>().empty()) {
        return ValidationResult::invalid("INVALID_ARGS", "url must be a non-empty string");
    }

    const std::string url = call.args.at("url").get<std::string>();
    if (url.rfind("https://", 0) != 0 && url.rfind("http://", 0) != 0) {
        return ValidationResult::invalid("INVALID_ARGS", "url must start with http:// or https://");
    }

    if (call.args.contains("action")) {
        if (!call.args.at("action").is_string()) {
            return ValidationResult::invalid("INVALID_ARGS", "action must be a string");
        }

        static const std::unordered_set<std::string> allowedActions = {
            "open"
        };

        const std::string action = call.args.at("action").get<std::string>();
        if (allowedActions.find(action) == allowedActions.end()) {
            return ValidationResult::invalid("INVALID_ARGS", "action is not supported");
        }
    }

    if (call.args.contains("site_id")) {
        if (!call.args.at("site_id").is_string() || call.args.at("site_id").get<std::string>().empty()) {
            return ValidationResult::invalid("INVALID_ARGS", "site_id must be a non-empty string");
        }
    }

    return ValidationResult::valid();
}

ValidationResult ArgsValidator::validateWebSearch(const ToolCall& call) const {
    if (!call.args.contains("query")) {
        return ValidationResult::invalid("MISSING_ARG", "Missing required arg: query");
    }

    if (!call.args.at("query").is_string() || call.args.at("query").get<std::string>().empty()) {
        return ValidationResult::invalid("INVALID_ARGS", "query must be a non-empty string");
    }

    if (!call.args.contains("url")) {
        return ValidationResult::invalid("MISSING_ARG", "Missing required arg: url");
    }

    if (!call.args.at("url").is_string() || call.args.at("url").get<std::string>().empty()) {
        return ValidationResult::invalid("INVALID_ARGS", "url must be a non-empty string");
    }

    const std::string url = call.args.at("url").get<std::string>();
    if (url.rfind("https://www.google.com/search?", 0) != 0) {
        return ValidationResult::invalid("INVALID_ARGS", "url must be a Google search URL");
    }

    if (call.args.contains("action")) {
        if (!call.args.at("action").is_string() || call.args.at("action").get<std::string>() != "search") {
            return ValidationResult::invalid("INVALID_ARGS", "action must be search");
        }
    }

    if (call.args.contains("provider")) {
        if (!call.args.at("provider").is_string() || call.args.at("provider").get<std::string>() != "google") {
            return ValidationResult::invalid("INVALID_ARGS", "provider must be google");
        }
    }

    return ValidationResult::valid();
}

ValidationResult ArgsValidator::validateWindowControl(const ToolCall& call) const {
    if (!call.args.contains("action")) {
        return ValidationResult::invalid("MISSING_ARG", "Missing required arg: action");
    }

    if (!call.args.at("action").is_string()) {
        return ValidationResult::invalid("INVALID_ARGS", "action must be a string");
    }

    static const std::unordered_set<std::string> allowedActions = {
        "close",
        "minimize",
        "maximize",
        "restore"
    };

    const std::string action = call.args.at("action").get<std::string>();
    if (allowedActions.find(action) == allowedActions.end()) {
        return ValidationResult::invalid("INVALID_ARGS", "action is not supported");
    }

    if (!call.args.contains("target_type")) {
        return ValidationResult::invalid("MISSING_ARG", "Missing required arg: target_type");
    }

    if (!call.args.at("target_type").is_string()) {
        return ValidationResult::invalid("INVALID_ARGS", "target_type must be a string");
    }

    const std::string targetType = call.args.at("target_type").get<std::string>();
    if (targetType == "current") {
        return ValidationResult::valid();
    }

    if (targetType == "app") {
        if (!call.args.contains("app_id")) {
            return ValidationResult::invalid("MISSING_ARG", "Missing required arg: app_id");
        }

        if (!call.args.at("app_id").is_string() || call.args.at("app_id").get<std::string>().empty()) {
            return ValidationResult::invalid("INVALID_ARGS", "app_id must be a non-empty string");
        }

        return ValidationResult::valid();
    }

    return ValidationResult::invalid("INVALID_ARGS", "target_type must be current or app");
}

ValidationResult ArgsValidator::validateWindowLayout(const ToolCall& call) const {
    if (!call.args.contains("layout")) {
        return ValidationResult::invalid("MISSING_ARG", "Missing required arg: layout");
    }

    if (!call.args.at("layout").is_string()) {
        return ValidationResult::invalid("INVALID_ARGS", "layout must be a string");
    }

    static const std::unordered_set<std::string> allowedLayouts = {
        "left_half",
        "right_half",
        "top_half",
        "bottom_half",
        "center",
        "fullscreen",
        "split_2_vertical",
        "split_2_horizontal",
        "grid_2x2"
    };

    const std::string layout = call.args.at("layout").get<std::string>();
    if (allowedLayouts.find(layout) == allowedLayouts.end()) {
        return ValidationResult::invalid("INVALID_ARGS", "layout is not supported");
    }

    if (!call.args.contains("targets")) {
        return ValidationResult::invalid("MISSING_ARG", "Missing required arg: targets");
    }

    if (!call.args.at("targets").is_array()) {
        return ValidationResult::invalid("INVALID_ARGS", "targets must be an array");
    }

    const auto& targets = call.args.at("targets");
    const size_t required = layout == "grid_2x2"
        ? 4
        : (layout == "split_2_vertical" || layout == "split_2_horizontal" ? 2 : 1);

    if (targets.size() < required) {
        return ValidationResult::invalid("MISSING_ARG", "Not enough targets for layout");
    }

    for (const auto& target : targets) {
        if (!target.is_string() || target.get<std::string>().empty()) {
            return ValidationResult::invalid("INVALID_ARGS", "targets must contain non-empty strings");
        }
    }

    return ValidationResult::valid();
}

ValidationResult ArgsValidator::validateWindowSnap(const ToolCall& call) const {
    if (!call.args.contains("position")) {
        return ValidationResult::invalid("MISSING_ARG", "Missing required arg: position");
    }

    if (!call.args.at("position").is_string()) {
        return ValidationResult::invalid("INVALID_ARGS", "position must be a string");
    }

    static const std::unordered_set<std::string> allowedPositions = {
        "left",
        "right",
        "maximize",
        "minimize"
    };

    const std::string position = call.args.at("position").get<std::string>();
    if (allowedPositions.find(position) == allowedPositions.end()) {
        return ValidationResult::invalid("INVALID_ARGS", "position is not supported");
    }

    if (call.args.contains("app_query")) {
        if (!call.args.at("app_query").is_string() || call.args.at("app_query").get<std::string>().empty()) {
            return ValidationResult::invalid("INVALID_ARGS", "app_query must be a non-empty string");
        }
    }

    return ValidationResult::valid();
}
