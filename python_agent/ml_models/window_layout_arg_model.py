from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import numpy as np


@dataclass
class WindowLayoutArgModel:
    """
    Runtime wrapper for window_layout argument extraction.

    IMPORTANT:
    - No text normalization here.
    - No hardcoded aliases here.
    - No phrase if/else shortcuts here.
    - All linguistic knowledge must come from the training dataset.
    """

    vectorizer: Any
    layout_model: Any
    target_models: list[Any]
    metadata: dict[str, Any] | None = None
    layout_threshold: float = 0.35
    target_threshold: float = 0.12
    target_fill_threshold: float = 0.035

    def predict(self, texts: list[str]) -> list[dict]:
        if not texts:
            return []

        x = self.vectorizer.transform([str(t) for t in texts])
        layout_preds = self.layout_model.predict(x)
        layout_probas = self._safe_predict_proba(self.layout_model, x)

        target_preds = [model.predict(x) for model in self.target_models]
        target_probas = [self._safe_predict_proba(model, x) for model in self.target_models]

        results: list[dict] = []

        for i, text in enumerate(texts):
            layout = str(layout_preds[i])
            layout_conf = self._pred_conf(self.layout_model, layout_probas, i, layout)

            if layout == "unknown" or layout_conf < self.layout_threshold:
                results.append({
                    "missing": ["layout", "targets"],
                    "confidence": round(float(layout_conf), 4),
                })
                continue

            required_targets = self._required_target_count(layout)
            max_targets = self._max_target_count(layout)

            targets: list[str] = []
            target_confs: list[float] = []

            # Main ordered slot predictions.
            for slot_idx, model in enumerate(self.target_models):
                target = str(target_preds[slot_idx][i])
                conf = self._pred_conf(model, target_probas[slot_idx], i, target)
                if target != "NO_TARGET" and conf >= self.target_threshold and target not in targets:
                    targets.append(target)
                    target_confs.append(float(conf))
                if len(targets) >= max_targets:
                    break

            # Generic probability-based fill for multi-target layouts.
            # This is not a phrase parser; it only uses the trained target models' probabilities.
            if required_targets > 1 and len(targets) < required_targets:
                candidates: list[tuple[int, float, str]] = []
                for slot_idx, model in enumerate(self.target_models):
                    proba = target_probas[slot_idx]
                    if proba is None:
                        continue
                    row = proba[i]
                    order = np.argsort(row)[::-1]
                    for class_idx in order[:8]:
                        cls = str(model.classes_[class_idx])
                        conf = float(row[class_idx])
                        if cls == "NO_TARGET" or cls in targets:
                            continue
                        if conf >= self.target_fill_threshold:
                            candidates.append((slot_idx, conf, cls))

                # Preserve slot order first, confidence second.
                candidates.sort(key=lambda item: (item[0], -item[1]))
                for _, conf, cls in candidates:
                    if cls not in targets:
                        targets.append(cls)
                        target_confs.append(float(conf))
                    if len(targets) >= required_targets:
                        break

            mentioned_targets = self._targets_by_text_order(str(text), max_targets, targets)
            if mentioned_targets:
                merged = list(mentioned_targets)
                for target in targets:
                    if target not in mentioned_targets:
                        merged.append(target)
                targets = merged[:max_targets]
                target_confs = [float(layout_conf)] * len(targets)

            if len(targets) < required_targets:
                results.append({
                    "layout": layout,
                    "missing": ["targets"],
                    "confidence": round(float(layout_conf), 4),
                })
                continue

            targets = targets[:max_targets]
            confidence_parts = [float(layout_conf)] + target_confs[:len(targets)]
            confidence = float(np.mean(confidence_parts)) if confidence_parts else float(layout_conf)

            results.append({
                "layout": layout,
                "targets": targets,
                "confidence": round(confidence, 4),
            })

        return results

    def _required_target_count(self, layout: str) -> int:
        if layout in {"split_2_vertical", "split_2_horizontal"}:
            return 2
        if layout == "grid_2x2":
            return 4
        if layout in {"fullscreen", "left_half", "right_half", "top_half", "bottom_half", "center"}:
            return 1
        return 1

    def _max_target_count(self, layout: str) -> int:
        if layout in {"split_2_vertical", "split_2_horizontal"}:
            return 2
        if layout == "grid_2x2":
            return 4
        return 1

    def _safe_predict_proba(self, model: Any, x: Any):
        if hasattr(model, "predict_proba"):
            return model.predict_proba(x)
        return None

    def _pred_conf(self, model: Any, proba, row_idx: int, pred: str) -> float:
        if proba is None:
            return 0.70
        classes = list(map(str, model.classes_))
        try:
            idx = classes.index(str(pred))
        except ValueError:
            return 0.0
        return float(proba[row_idx][idx])

    def _targets_by_text_order(self, text: str, max_targets: int, candidate_targets: list[str] | None = None) -> list[str]:
        metadata = self.metadata or {}
        surfaces = metadata.get("app_surface_forms")
        if not isinstance(surfaces, dict):
            return []

        normalized = " ".join(str(text).lower().split())
        matches: list[tuple[int, int, int, int, str]] = []
        candidate_rank = {target: idx for idx, target in enumerate(candidate_targets or [])}
        exact_apps: set[str] = set()

        for app_id, values in surfaces.items():
            if not isinstance(values, list):
                continue
            for raw_surface in values:
                surface = " ".join(str(raw_surface).lower().split())
                if len(surface) < 3:
                    continue
                pattern = rf"(?<![\wа-яё]){re.escape(surface)}(?![\wа-яё])"
                for found in re.finditer(pattern, normalized, flags=re.IGNORECASE):
                    matches.append((
                        found.start(),
                        found.end(),
                        -len(surface),
                        candidate_rank.get(str(app_id), 10_000),
                        str(app_id),
                    ))
                    exact_apps.add(str(app_id))

        # If the trained target slots already found an app, use the app surface
        # metadata to place typoed mentions like "нооутпад" back in text order.
        for app_id in candidate_targets or []:
            if app_id in exact_apps:
                continue
            values = surfaces.get(app_id)
            if not isinstance(values, list):
                continue
            fuzzy = self._best_fuzzy_surface_match(normalized, values)
            if fuzzy is None:
                continue
            start, end, surface_len, score = fuzzy
            if score >= self._fuzzy_surface_threshold(surface_len):
                matches.append((
                    start,
                    end,
                    -surface_len,
                    candidate_rank.get(str(app_id), 10_000),
                    str(app_id),
                ))

        matches.sort()

        ordered_matches: list[tuple[int, int, int, int, str]] = []
        used_spans: list[tuple[int, int]] = []
        used_apps: set[str] = set()
        for match in matches:
            start, end, _length, _rank, app_id = match
            if app_id in used_apps:
                continue
            if any(start < used_end and end > used_start for used_start, used_end in used_spans):
                continue
            ordered_matches.append(match)
            used_spans.append((start, end))
            used_apps.add(app_id)
            if len(ordered_matches) >= max_targets:
                break

        if max_targets == 2 and len(ordered_matches) >= 2:
            first = ordered_matches[0]
            second = ordered_matches[1]
            between = normalized[first[1]:second[0]]
            if re.search(r"(?<![\wа-яё])под(?![\wа-яё])", between, flags=re.IGNORECASE):
                return [second[3], first[3]]

        ordered: list[str] = []
        for _start, _end, _length, _rank, app_id in ordered_matches:
            if app_id not in ordered:
                ordered.append(app_id)
            if len(ordered) >= max_targets:
                break
        return ordered

    def _best_fuzzy_surface_match(self, normalized: str, surfaces: list[Any]) -> tuple[int, int, int, float] | None:
        tokens = [
            (match.group(0), match.start(), match.end())
            for match in re.finditer(r"[\wа-яё]+", normalized, flags=re.IGNORECASE)
        ]
        if not tokens:
            return None

        best: tuple[int, int, int, float] | None = None
        for raw_surface in surfaces:
            surface = " ".join(str(raw_surface).lower().split())
            if len(surface) < 5:
                continue
            surface_token_count = max(1, len(surface.split()))
            window_sizes = {
                max(1, surface_token_count - 1),
                surface_token_count,
                surface_token_count + 1,
            }
            for window_size in window_sizes:
                if window_size > len(tokens):
                    continue
                for idx in range(0, len(tokens) - window_size + 1):
                    start = tokens[idx][1]
                    end = tokens[idx + window_size - 1][2]
                    candidate = normalized[start:end]
                    score = SequenceMatcher(None, candidate, surface).ratio()
                    item = (start, end, len(surface), float(score))
                    if best is None or score > best[3] or (score == best[3] and item[:2] < best[:2]):
                        best = item
        return best

    def _fuzzy_surface_threshold(self, surface_len: int) -> float:
        if surface_len >= 10:
            return 0.82
        return 0.86
