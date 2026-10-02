"""Natural-language property search → structured ``SearchFilters`` (rule based).

Understands common Iraqi Arabic and English phrasing: purpose (للبيع/للإيجار),
property types and synonyms (بيت/منزل/دار…), rooms in digits or words
(غرفتين، ثلاث غرف), areas, prices with units (مليون/ألف/$) and comparators
(أقل من/تحت/بين…), amenities, verified-only and known place names.

It never guesses: an amount without a currency is reported as an ambiguity
and not applied (IQD and USD are never assumed or converted). Everything that
was applied is listed in ``understood`` so the user can see and correct the
interpretation.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

_DIACRITICS = re.compile(r"[ً-ْٰـ]")
_TRANSLATE = str.maketrans("أإآٱىة٠١٢٣٤٥٦٧٨٩", "اااايه0123456789")


def normalize(text: str) -> str:
    """Python twin of the SQL ``normalize_ar`` function."""
    text = _DIACRITICS.sub("", text).translate(_TRANSLATE).lower()
    text = text.replace("،", " ").replace(",", "")
    return re.sub(r"\s+", " ", text).strip()


TYPE_SYNONYMS: dict[str, list[str]] = {
    "APARTMENT": ["شقه", "شقق", "apartment", "apartments", "flat", "flats"],
    "HOUSE": ["بيت", "بيوت", "منزل", "منازل", "دار", "house", "houses", "home"],
    "VILLA": ["فيلا", "فلل", "فله", "villa", "villas"],
    "LAND": ["ارض", "اراضي", "قطعه ارض", "قطعه", "land", "plot"],
    "BUILDING": ["بنايه", "عماره", "building"],
    "SHOP": ["محل", "محلات", "دكان", "shop", "store"],
    "OFFICE": ["مكتب", "مكاتب", "office"],
    "WAREHOUSE": ["مخزن", "مخازن", "مستودع", "warehouse"],
    "FACTORY": ["معمل", "مصنع", "factory"],
    "FARM": ["مزرعه", "بستان", "farm", "orchard"],
}

AMENITY_SYNONYMS: dict[str, list[str]] = {
    "SWIMMING_POOL": ["مسبح", "pool", "swimming pool"],
    "GARDEN": ["حديقه", "حديقة", "garden"],
    "GARAGE": ["كراج", "گراج", "garage"],
    "PARKING": ["موقف سيارات", "موقف", "parking"],
    "PRIVATE_GENERATOR": ["مولده", "مولد", "generator"],
    "ELEVATOR": ["مصعد", "اسانسير", "elevator", "lift"],
    "SOLAR_PANELS": ["طاقه شمسيه", "الواح شمسيه", "solar"],
    "CENTRAL_AC": ["تبريد مركزي", "تكييف مركزي", "central ac", "central air"],
    "BALCONY": ["بالكونه", "شرفه", "balcony"],
    "CORNER_PLOT": ["ركن", "زاويه", "corner"],
}

_NUM_WORDS = {
    "واحد": 1, "واحده": 1, "اثنين": 2, "اثنتين": 2, "ثنين": 2, "ثلاث": 3, "ثلاثه": 3,
    "اربع": 4, "اربعه": 4, "خمس": 5, "خمسه": 5, "ست": 6, "سته": 6, "سبع": 7, "سبعه": 7,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
}  # fmt: skip

_UNIT = r"(مليون|ملايين|million|m|الف|الاف|k|thousand|مليار|billion)?"
_NUMBER = r"(\d+(?:\.\d+)?)"
_LESS = r"(?:اقل من|اقل|تحت|لا يتجاوز|الى حد|حد اقصى|بحدود|under|below|less than|max|up to|upto)"
_MORE = r"(?:اكثر من|فوق|من|ابتداء من|على الاقل|above|over|more than|min|at least|from)"


def _amount(number: str, unit: str | None) -> Decimal:
    value = Decimal(number)
    unit = (unit or "").lower()
    if unit in ("مليون", "ملايين", "million", "m"):
        value *= 1_000_000
    elif unit in ("الف", "الاف", "k", "thousand"):
        value *= 1_000
    elif unit in ("مليار", "billion"):
        value *= 1_000_000_000
    return value


def _currency(text: str) -> str | None:
    if re.search(r"(\$|دولار|usd|dollar|ورقه|ورقة)", text):
        return "USD"
    if re.search(r"(دينار|د\.ع|iqd|dinar)", text):
        return "IQD"
    return None


def parse(query: str, vocabulary: dict[str, Any]) -> dict[str, Any]:
    text = normalize(query)
    consumed: list[tuple[int, int]] = []
    filters: dict[str, Any] = {}
    understood: list[dict[str, str]] = []
    ambiguities: list[str] = []

    def overlaps(span: tuple[int, int]) -> bool:
        return any(s < span[1] and span[0] < e for s, e in consumed)

    def found(pattern: str) -> re.Match[str] | None:
        for match in re.finditer(pattern, text):
            if not overlaps(match.span()):
                consumed.append(match.span())
                return match
        return None

    def note(field: str, value: Any, phrase: str) -> None:
        understood.append({"field": field, "value": str(value), "phrase": phrase})

    # Purpose and rent period
    if m := found(r"(للبيع|بيع|شراء|for sale|to buy|\bbuy\b|\bsale\b)"):
        filters["purpose"] = "SALE"
        note("purpose", "SALE", m.group(0))
    if m := found(r"(للايجار|ايجار|اجار|للاجار|for rent|to rent|\brent\b|rental)"):
        filters["purpose"] = "RENT"
        note("purpose", "RENT", m.group(0))
        if m2 := found(r"(شهري|monthly|يومي|daily|سنوي|yearly|annual)"):
            period = {"شهري": "MONTHLY", "monthly": "MONTHLY", "يومي": "DAILY", "daily": "DAILY"}
            filters["rent_period"] = period.get(m2.group(0), "YEARLY")
            note("rent_period", filters["rent_period"], m2.group(0))

    # Property types (longest synonyms first)
    types: list[str] = []
    for code, words in TYPE_SYNONYMS.items():
        for word in sorted(words, key=len, reverse=True):
            if found(rf"(?<!\w){re.escape(word)}(?!\w)"):
                types.append(code)
                note("property_types", code, word)
                break
    if types:
        filters["property_types"] = sorted(set(types))

    # Bedrooms / bathrooms (digits, number words, or Arabic duals)
    word_alt = "|".join(sorted(_NUM_WORDS, key=len, reverse=True))

    def rooms(pattern: str, dual: str, field: str) -> None:
        value: int | None = None
        if m := found(rf"{_NUMBER}\s*{pattern}"):
            value = int(float(m.group(1)))
        elif m := found(rf"(?:({word_alt})\s*{pattern})|(?:{pattern}\s*({word_alt}))"):
            value = _NUM_WORDS[m.group(1) or m.group(2)]
        elif m := found(dual):
            value = 2
        if m is not None and value is not None and 0 <= value <= 50:
            filters[field] = value
            note(field, value, m.group(0))

    rooms(
        r"(?:غرف نوم|غرفه نوم|غرف|غرفه|bedrooms|bedroom|beds|bed|br)(?!\w)",
        r"(?:غرفتين|غرفتان)(?!\w)",
        "bedrooms_min",
    )
    rooms(r"(?:حمامات|حمام|bathrooms|bathroom|baths|bath)(?!\w)", r"حمامين(?!\w)", "bathrooms_min")

    # Area
    area_unit = r"(?:م2|م²|متر مربع|متر|m2|sqm|square meters|square metres)(?!\w)"
    if m := found(rf"(?:({_LESS}|{_MORE})\s*)?{_NUMBER}\s*{area_unit}"):
        qualifier, number = m.group(1), Decimal(m.group(2))
        if qualifier and re.fullmatch(_LESS, qualifier):
            filters["max_area"] = str(number)
            note("max_area", number, m.group(0))
        elif qualifier and re.fullmatch(_MORE, qualifier):
            filters["min_area"] = str(number)
            note("min_area", number, m.group(0))
        else:
            filters["min_area"] = str((number * Decimal("0.9")).quantize(Decimal(1)))
            filters["max_area"] = str((number * Decimal("1.1")).quantize(Decimal(1)))
            note("area_about", f"{number} ±10%", m.group(0))

    # Price: an amount with a unit, a currency marker or a comparator
    currency = _currency(text)
    price: dict[str, Decimal] = {}
    phrase = ""
    if m := found(
        rf"(?:بين|between)\s*{_NUMBER}\s*{_UNIT}\s*(?:و|الى|-|and|to)\s*{_NUMBER}\s*{_UNIT}"
    ):
        price["min_price"] = _amount(m.group(1), m.group(2) or m.group(4))
        price["max_price"] = _amount(m.group(3), m.group(4))
        phrase = m.group(0)
    else:
        for match in re.finditer(
            rf"(?:({_LESS}|{_MORE})\s*)?(\$\s*)?{_NUMBER}\s*{_UNIT}\s*(\$|دولار|دينار|usd|iqd|ورقه)?",
            text,
        ):
            comparator, dollar, amount_text, unit, marker = match.groups()
            if overlaps(match.span()) or not (comparator or dollar or unit or marker):
                continue
            consumed.append(match.span())
            value = _amount(amount_text, unit)
            if comparator and re.fullmatch(_MORE, comparator):
                price["min_price"] = value
            else:
                price["max_price"] = value  # a plain amount reads as a budget ceiling
            phrase = match.group(0)
            break
    if price:
        if currency is None:
            ambiguities.append("currency_not_specified")
        else:
            filters["currency"] = currency
            for key, amount in price.items():
                filters[key] = str(amount.quantize(Decimal(1)))
                note(key, f"{amount:,.0f} {currency}", phrase.strip())

    # Amenities and furnishing
    amenities: list[str] = []
    for code, words in AMENITY_SYNONYMS.items():
        for word in sorted(words, key=len, reverse=True):
            if found(rf"(?<!\w){re.escape(normalize(word))}(?!\w)"):
                amenities.append(code)
                note("amenities", code, word)
                break
    if amenities:
        filters["amenities"] = sorted(set(amenities))
    if m := found(r"(غير مفروش|unfurnished)"):
        filters["furnishing"] = "UNFURNISHED"
        note("furnishing", "UNFURNISHED", m.group(0))
    else:
        if m := found(r"(نصف مفروش|semi furnished|semi-furnished)"):
            filters["furnishing"] = "SEMI_FURNISHED"
            note("furnishing", "SEMI_FURNISHED", m.group(0))
        else:
            if m := found(r"(مفروش|مفروشه|furnished)"):
                filters["furnishing"] = "FURNISHED"
                note("furnishing", "FURNISHED", m.group(0))
    if m := found(r"(موثق|موثقه|verified)"):
        filters["verified_only"] = True
        note("verified_only", True, m.group(0))
    if m := found(r"(جديد|جديده|new build|brand new)"):
        filters["condition"] = "NEW"
        note("condition", "NEW", m.group(0))

    # Places: most specific level first, longest names first
    for level, field in (
        ("neighborhoods", "neighborhood_id"),
        ("districts", "district_id"),
        ("cities", "city_id"),
        ("governorates", "governorate_id"),
    ):
        entries = vocabulary.get(level) or []
        candidates = sorted(
            ((normalize(name), entry) for entry in entries for name in entry["names"] if name),
            key=lambda pair: len(pair[0]),
            reverse=True,
        )
        for name, entry in candidates:
            if len(name) < 3:
                continue
            base = re.escape(name.removeprefix("ال"))
            if m := found(rf"(?<!\w)[وبل]?(?:ال)?{base}(?!\w)"):
                filters[field] = entry["id"]
                note(field, entry["names"][0], m.group(0))
                break
        if field in filters and level in ("neighborhoods", "districts", "cities"):
            break  # a specific place implies its parents

    leftover = text
    for start, end in sorted(consumed, reverse=True):
        leftover = leftover[:start] + " " + leftover[end:]
    stop = {
        "في", "ب", "مع", "و", "او", "ال", "عن", "اريد", "ابحث", "ابي", "in", "with", "a",
        "an", "the", "for", "and", "near", "قرب", "منطقه", "حي", "دينار", "دولار", "$", "iqd",
        "usd", "سعر", "بسعر", "price", "budget", "ميزانيه", "looking", "i", "want",
    }  # fmt: skip
    unparsed = [w for w in re.split(r"\s+", leftover) if w and w not in stop and len(w) > 1]
    total = len([w for w in text.split() if w not in stop]) or 1
    confidence = round(max(0.0, min(1.0, 1 - len(unparsed) / total)), 2)
    return {
        "filters": filters,
        "understood": understood,
        "ambiguities": ambiguities,
        "unparsed": " ".join(unparsed),
        "confidence": confidence,
    }
