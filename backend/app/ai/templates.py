"""Deterministic generators used by ``MockAIProvider``.

Each builder receives only the *facts* dictionary and must not add anything
that is not in it: a missing fact is simply not mentioned. Output shapes match
the JSON schemas the real providers are asked for.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app.ai import nlsearch

Builder = Callable[[dict[str, Any], str], dict[str, Any]]


def _join_ar(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return "، ".join(items[:-1]) + " و" + items[-1]


def _join_en(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _where(f: dict[str, Any], lang: str) -> str:
    keys = ("neighborhood", "district", "city")
    parts = [f.get(f"{k}_{lang}") or f.get(f"{k}_ar") for k in keys]
    sep = "، " if lang == "ar" else ", "
    return sep.join(p for p in parts if p)


def _rooms(f: dict[str, Any], lang: str) -> list[str]:
    out = []
    if f.get("bedrooms") is not None:
        out.append(f"{f['bedrooms']} غرف نوم" if lang == "ar" else f"{f['bedrooms']} bedrooms")
    if f.get("bathrooms") is not None:
        out.append(f"{f['bathrooms']} حمامات" if lang == "ar" else f"{f['bathrooms']} bathrooms")
    if f.get("area_m2"):
        out.append(f"بمساحة {f['area_m2']} م²" if lang == "ar" else f"{f['area_m2']} m²")
    if f.get("land_area_m2"):
        out.append(
            f"على أرض {f['land_area_m2']} م²"
            if lang == "ar"
            else f"on a {f['land_area_m2']} m² plot"
        )
    if f.get("floors") is not None:
        out.append(f"{f['floors']} طوابق" if lang == "ar" else f"{f['floors']} floors")
    return out


def listing_description(f: dict[str, Any], lang: str) -> dict[str, Any]:
    type_ = f.get(f"type_{lang}") or f.get("type_ar") or ""
    purpose = f.get(f"purpose_{lang}") or ""
    where = _where(f, lang)
    rooms = _rooms(f, lang)
    amenities = f.get(f"amenities_{lang}") or []
    sentences: list[str] = []
    if lang == "ar":
        head = f"{type_} {purpose}".strip()
        sentences.append(f"{head} في {where}." if where else f"{head}.")
        if rooms:
            sentences.append(f"يتكوّن العقار من {_join_ar(rooms)}.")
        if f.get("condition_ar"):
            sentences.append(f"الحالة: {f['condition_ar']}.")
        if f.get("furnishing_ar"):
            sentences.append(f"الأثاث: {f['furnishing_ar']}.")
        if f.get("year_built"):
            sentences.append(f"سنة البناء: {f['year_built']}.")
        if amenities:
            sentences.append(f"من المزايا: {_join_ar(amenities)}.")
        if f.get("price_text"):
            sentences.append(f"السعر المطلوب: {f['price_text']}.")
        sentences.append("للاستفسار أو ترتيب معاينة، تواصل مع المعلن.")
    else:
        head = f"{type_} {purpose}".strip()
        sentences.append(f"{head} in {where}." if where else f"{head}.")
        if rooms:
            sentences.append(f"It offers {_join_en(rooms)}.")
        if f.get("condition_en"):
            sentences.append(f"Condition: {f['condition_en']}.")
        if f.get("furnishing_en"):
            sentences.append(f"Furnishing: {f['furnishing_en']}.")
        if f.get("year_built"):
            sentences.append(f"Built in {f['year_built']}.")
        if amenities:
            sentences.append(f"Amenities include {_join_en(amenities)}.")
        if f.get("price_text"):
            sentences.append(f"Asking price: {f['price_text']}.")
        sentences.append("Contact the lister for questions or to arrange a viewing.")
    highlights = (rooms + amenities)[:6]
    return {"description": " ".join(sentences), "highlights": highlights}


def listing_title(f: dict[str, Any], lang: str) -> dict[str, Any]:
    type_ = f.get(f"type_{lang}") or f.get("type_ar") or ""
    purpose = f.get(f"purpose_{lang}") or ""
    place = f.get(f"district_{lang}") or f.get("district_ar") or f.get(f"city_{lang}") or ""
    titles = []
    if lang == "ar":
        titles.append(f"{type_} {purpose} في {place}".strip() if place else f"{type_} {purpose}")
        if f.get("area_m2"):
            titles.append(f"{type_} {f['area_m2']} م² {purpose}".strip())
        if f.get("bedrooms") is not None:
            titles.append(f"{type_} {f['bedrooms']} غرف نوم {purpose}".strip())
    else:
        titles.append(f"{type_} {purpose} in {place}".strip() if place else f"{type_} {purpose}")
        if f.get("area_m2"):
            titles.append(f"{f['area_m2']} m² {type_} {purpose}".strip())
        if f.get("bedrooms") is not None:
            titles.append(f"{f['bedrooms']}-bedroom {type_} {purpose}".strip())
    return {"titles": [re.sub(r"\s+", " ", t)[:120] for t in titles]}


_AR_PUNCT = [(r"\s*,\s*", "، "), (r"\s*\?\s*", "؟ "), (r"\s*;\s*", "؛ ")]


def improve_arabic(f: dict[str, Any], lang: str) -> dict[str, Any]:
    """Light, meaning-preserving clean-up: spacing, Arabic punctuation, repeats."""
    text = str(f.get("text", ""))
    text = re.sub(r"([!؟?.،,])\1+", r"\1", text)
    for pattern, repl in _AR_PUNCT:
        text = re.sub(pattern, repl, text)
    text = re.sub(r"\s+([.،؟!])", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if text and text[-1] not in ".!؟":
        text += "."
    return {"text": text, "changes": ["spacing", "punctuation"]}


def property_summary(f: dict[str, Any], lang: str) -> dict[str, Any]:
    type_ = f.get(f"type_{lang}") or f.get("type_ar") or ""
    purpose = f.get(f"purpose_{lang}") or ""
    where = _where(f, lang)
    bullets = _rooms(f, lang)
    if f.get("price_text"):
        bullets.append(
            (f"السعر: {f['price_text']}") if lang == "ar" else f"Price: {f['price_text']}"
        )
    if f.get("verified"):
        bullets.append("إعلان موثّق" if lang == "ar" else "Verified listing")
    if lang == "ar":
        summary = f"{type_} {purpose} في {where}".strip() if where else f"{type_} {purpose}"
    else:
        summary = f"{type_} {purpose} in {where}".strip() if where else f"{type_} {purpose}"
    return {"summary": re.sub(r"\s+", " ", summary), "bullets": bullets}


def lead_reply(f: dict[str, Any], lang: str) -> dict[str, Any]:
    name = f.get("customer_name") or ""
    title = f.get("property_title") or ""
    if lang == "ar":
        parts = [f"مرحباً {name}،".strip("، ") + "،" if name else "مرحباً،"]
        parts.append(f"شكراً لاهتمامك بـ «{title}»." if title else "شكراً لتواصلك معنا.")
        if f.get("property_listed"):
            parts.append("الإعلان ما زال منشوراً على المنصة.")
        parts.append("هل يناسبك تحديد موعد للمعاينة؟ يسعدني الإجابة عن أي سؤال.")
        if f.get("agent_name"):
            parts.append(f"مع التحية، {f['agent_name']}")
    else:
        parts = [f"Hello {name}," if name else "Hello,"]
        parts.append(
            f"Thank you for your interest in “{title}”." if title else "Thank you for reaching out."
        )
        if f.get("property_listed"):
            parts.append("The listing is still published on the platform.")
        parts.append("Would you like to arrange a viewing? Happy to answer any questions.")
        if f.get("agent_name"):
            parts.append(f"Best regards, {f['agent_name']}")
    return {"reply": "\n".join(parts)}


def lead_summary(f: dict[str, Any], lang: str) -> dict[str, Any]:
    items = []
    if lang == "ar":
        items.append(f"العميل: {f.get('customer_name', '')}")
        if f.get("property_title"):
            items.append(f"العقار: {f['property_title']}")
        items.append(f"المرحلة: {f.get('status', '')}")
        if f.get("activity_count") is not None:
            items.append(f"عدد الأنشطة المسجلة: {f['activity_count']}")
        if f.get("last_activity"):
            items.append(f"آخر نشاط: {f['last_activity']}")
    else:
        items.append(f"Customer: {f.get('customer_name', '')}")
        if f.get("property_title"):
            items.append(f"Property: {f['property_title']}")
        items.append(f"Stage: {f.get('status', '')}")
        if f.get("activity_count") is not None:
            items.append(f"Logged activities: {f['activity_count']}")
        if f.get("last_activity"):
            items.append(f"Last activity: {f['last_activity']}")
    return {"summary": " · ".join(items)}


def search_parse(f: dict[str, Any], lang: str) -> dict[str, Any]:
    return nlsearch.parse(str(f.get("query", "")), f.get("vocabulary") or {})


BUILDERS: dict[str, Builder] = {
    "listing.description": listing_description,
    "listing.title": listing_title,
    "text.improve_ar": improve_arabic,
    "property.summary": property_summary,
    "lead.reply": lead_reply,
    "lead.summary": lead_summary,
    "search.parse": search_parse,
}
