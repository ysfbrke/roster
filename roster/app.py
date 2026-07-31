from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
ASSET_DIR = APP_DIR / "assets"

NAVY = "#071A33"
NAVY_2 = "#0B2545"
ACCENT = "#5DD3FF"
TEXT = "#F8FAFC"
MUTED = "#C9D6E8"

ROLE_ADMIN = "admin"
ROLE_PLANNER = "planner"

DAY_NAMES_TR = {
    0: "Pazartesi",
    1: "Salı",
    2: "Çarşamba",
    3: "Perşembe",
    4: "Cuma",
    5: "Cumartesi",
    6: "Pazar",
}

BASE_COLUMN_ALIASES = {
    "employee": ["Employee Number", "Sicil", "Sicil No", "Sicil Numarası"],
    "first_name": ["First Name", "İlk Adı", "Isim", "İsim", "Ad"],
    "last_name": ["Last Name", "Soyadı", "Soyad"],
    "district": ["District", "Servis", "Servis Kodu", "Güzergah", "Guzergah"],
    "group": ["Team or Employee Group", "Grup", "Group"],
    "total_planned": ["Total Planned Working Time", "Toplam Çalışma", "Planlanan Saat"],
    "total_target": ["Total Target Working Time", "Hedef Saat", "Target"],
    "days_off": ["Number of Days off", "Off Gün", "Off Gün Sayısı"],
}


def get_admin_password() -> str:
    try:
        return str(st.secrets.get("ADMIN_PASSWORD", "ayferberat32"))
    except Exception:
        return "ayferberat32"


def set_page_style() -> None:
    st.set_page_config(page_title="Çelebi Roster Planlama", page_icon="✈️", layout="wide")
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
              radial-gradient(circle at top left, rgba(93, 211, 255, .16), transparent 28%),
              linear-gradient(135deg, {NAVY} 0%, #020817 100%);
            color: {TEXT};
        }}
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #06162A 0%, #031020 100%);
            border-right: 1px solid rgba(255,255,255,.08);
        }}
        .block-container {{ padding-top: 1.3rem; padding-bottom: 2rem; }}
        .hero {{
            background: linear-gradient(90deg, rgba(16,42,76,.95), rgba(7,26,51,.65));
            border: 1px solid rgba(255,255,255,.10);
            border-radius: 24px;
            padding: 22px 24px;
            margin-bottom: 18px;
            box-shadow: 0 14px 32px rgba(0,0,0,.25);
        }}
        .hero h1 {{ margin: 0; font-size: 34px; letter-spacing: .2px; color:white; }}
        .hero p {{ margin: 8px 0 0 0; color: {MUTED}; font-size: 16px; }}
        .pill {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 999px;
            background: rgba(93, 211, 255, .14);
            color: #BEEBFF;
            border: 1px solid rgba(93, 211, 255, .35);
            font-size: 12px;
            margin-right: 8px;
        }}
        div[data-testid="stMetric"] {{
            background: rgba(16,42,76,.82);
            border: 1px solid rgba(255,255,255,.09);
            padding: 18px 18px 14px 18px;
            border-radius: 18px;
            box-shadow: 0 10px 24px rgba(0,0,0,.22);
        }}
        div[data-testid="stMetricValue"] {{ color: #FFFFFF; }}
        div[data-testid="stMetricLabel"] {{ color: {MUTED}; }}
        .warning-card {{
            background: rgba(245, 158, 11, .12);
            border: 1px solid rgba(245, 158, 11, .45);
            color: #FFE9B4;
            border-radius: 18px;
            padding: 16px 18px;
            margin: 10px 0 14px 0;
        }}
        h1, h2, h3, h4, p, label, span {{ color: inherit; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def logo_header() -> None:
    logo_path = ASSET_DIR / "celebi_logo.svg"
    col1, col2 = st.columns([1, 7])
    with col1:
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        else:
            st.markdown("### ÇELEBİ")
    with col2:
        st.markdown(
            """
            <div class="hero">
                <div><span class="pill">Roster</span><span class="pill">Servis Planlama</span><span class="pill">Haftalık Saat Kontrolü</span></div>
                <h1>Çelebi Akıllı Roster Planlama Sistemi</h1>
                <p>Servis planlama tüm yüklenen günleri okur; haftalık saat hesabı yeni haftanın 7 gününe göre yapılır.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def current_role_label() -> str:
    return "Planlamacı" if st.session_state.get("user_role") == ROLE_PLANNER else "Yönetici"


def is_planner_mode() -> bool:
    return st.session_state.get("user_role") == ROLE_PLANNER


def render_login_page() -> bool:
    logo_path = ASSET_DIR / "celebi_logo.svg"
    c1, c2 = st.columns([1, 5])
    with c1:
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        else:
            st.markdown("### ÇELEBİ")

    with c2:
        st.markdown(
            """
            <div class="hero">
                <div><span class="pill">Yönetici</span><span class="pill">Planlamacı</span><span class="pill">Sicil Gizleme</span></div>
                <h1>Çelebi Roster Planlama Girişi</h1>
                <p>Yönetici tüm bilgileri görür. Planlamacı girişinde Employee Number / Sicil gizlenir.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    admin_col, planner_col = st.columns(2)

    with admin_col:
        st.markdown("### 🔐 Yönetici Girişi")
        password = st.text_input("Yönetici şifresi", type="password", key="admin_password_input")
        if st.button("Yönetici olarak giriş yap", type="primary", use_container_width=True):
            if password == get_admin_password():
                st.session_state["user_role"] = ROLE_ADMIN
                st.rerun()
            else:
                st.error("Yönetici şifresi hatalı.")

    with planner_col:
        st.markdown("### 🧭 Planlamacı Girişi")
        st.caption("Şifre yoktur. Employee Number / Sicil hiçbir ekranda gösterilmez.")
        if st.button("Planlamacı olarak giriş yap", use_container_width=True):
            st.session_state["user_role"] = ROLE_PLANNER
            st.rerun()

    return False


def require_login() -> bool:
    if st.session_state.get("user_role") in {ROLE_ADMIN, ROLE_PLANNER}:
        return True
    return render_login_page()


def normalize_col_name(col: object) -> str:
    if isinstance(col, datetime):
        return col.strftime("%Y%m%d")

    text = str(col).strip()

    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]

    return text


def read_roster_excel(file_obj) -> tuple[pd.DataFrame, str]:
    file_obj.seek(0)
    xls = pd.ExcelFile(file_obj)

    preferred = None
    for sheet_name in xls.sheet_names:
        if "roster" in sheet_name.lower():
            preferred = sheet_name
            break

    sheet_name = preferred or xls.sheet_names[0]

    file_obj.seek(0)
    df = pd.read_excel(file_obj, sheet_name=sheet_name, dtype=object)
    df.columns = [normalize_col_name(c) for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)

    return df, sheet_name


def find_col(df: pd.DataFrame, aliases: Iterable[str], fallback_index: int | None = None) -> str | None:
    normalized = {str(c).strip().lower(): str(c) for c in df.columns}

    for alias in aliases:
        key = alias.strip().lower()
        if key in normalized:
            return normalized[key]

    if fallback_index is not None and fallback_index < len(df.columns):
        return str(df.columns[fallback_index])

    return None


def parse_date_column(col: object) -> datetime | None:
    text = normalize_col_name(col)
    match = re.fullmatch(r"(20\d{6})", text)

    if not match:
        return None

    try:
        return datetime.strptime(match.group(1), "%Y%m%d")
    except ValueError:
        return None


def get_schema(df: pd.DataFrame) -> dict[str, object]:
    cols = [str(c) for c in df.columns]

    schema: dict[str, object] = {
        "employee": find_col(df, BASE_COLUMN_ALIASES["employee"], 0),
        "first_name": find_col(df, BASE_COLUMN_ALIASES["first_name"], 1),
        "last_name": find_col(df, BASE_COLUMN_ALIASES["last_name"], 2),
        "district": find_col(df, BASE_COLUMN_ALIASES["district"], 3),
        "group": find_col(df, BASE_COLUMN_ALIASES["group"], 4),
        "total_planned": find_col(
            df,
            BASE_COLUMN_ALIASES["total_planned"],
            len(cols) - 3 if len(cols) >= 3 else None,
        ),
        "total_target": find_col(
            df,
            BASE_COLUMN_ALIASES["total_target"],
            len(cols) - 2 if len(cols) >= 2 else None,
        ),
        "days_off": find_col(
            df,
            BASE_COLUMN_ALIASES["days_off"],
            len(cols) - 1 if len(cols) >= 1 else None,
        ),
    }

    day_cols: list[str] = []

    for col in cols:
        if parse_date_column(col) is not None:
            day_cols.append(col)

    if not day_cols and len(cols) >= 12:
        total_planned_col = schema.get("total_planned")
        if total_planned_col and str(total_planned_col) in cols:
            total_index = cols.index(str(total_planned_col))
            day_cols = cols[5:total_index]
        else:
            day_cols = cols[5:12]

    # Servis planlama tüm yüklenen günleri kullanır.
    # Örnek: geçmiş haftanın son günü + yeni haftanın 7 günü = 8 gün.
    schema["service_day_cols"] = day_cols

    # Roster düzenleme ve haftalık saat hesabı yeni haftanın 7 gününü kullanır.
    # Eğer 8 veya daha fazla gün varsa ilk gün geçmiş hafta kabul edilir ve hariç tutulur.
    if len(day_cols) >= 8:
        schema["day_cols"] = day_cols[1:8]
        schema["excluded_previous_day_col"] = day_cols[0]
    else:
        schema["day_cols"] = day_cols[:7]
        schema["excluded_previous_day_col"] = None

    return schema


def day_label(col: str) -> str:
    date_value = parse_date_column(col)

    if date_value:
        return f"{DAY_NAMES_TR[date_value.weekday()]} {date_value.strftime('%d.%m.%Y')}"

    return str(col)


def is_off_or_empty(value: object) -> bool:
    if value is None or pd.isna(value):
        return True

    text = str(value).strip()

    if text in {"", "-"}:
        return True

    upper = text.upper()

    return upper.startswith("DO") or upper in {"OFF", "REST", "İZİN", "IZIN"}


def raw_time_to_hhmm(raw: str) -> str:
    raw = raw.strip().zfill(4)
    return f"{raw[:2]}:{raw[2:]}"


def time_to_minutes(hhmm: str | None) -> int | None:
    if not hhmm:
        return None

    try:
        hour, minute = hhmm.split(":")
        return int(hour) * 60 + int(minute)
    except Exception:
        return None


def minutes_to_hhmm(minutes: int | float | None) -> str:
    if minutes is None or pd.isna(minutes):
        minutes = 0

    minutes_int = int(round(float(minutes)))
    sign = "-" if minutes_int < 0 else ""

    minutes_int = abs(minutes_int)

    return f"{sign}{minutes_int // 60:02d}:{minutes_int % 60:02d} h"


def parse_hours_to_minutes(value: object) -> int:
    if value is None or pd.isna(value):
        return 0

    text = str(value).strip()

    if not text:
        return 0

    bracket_match = re.search(
        r"\[\s*(\d{1,3})\s*:\s*(\d{1,2})\s*h?\s*\]",
        text,
        flags=re.IGNORECASE,
    )

    if bracket_match:
        return int(bracket_match.group(1)) * 60 + int(bracket_match.group(2))

    decimal_match = re.search(r"(\d+(?:[\.,]\d+)?)\s*h", text, flags=re.IGNORECASE)

    if decimal_match:
        return int(round(float(decimal_match.group(1).replace(",", ".")) * 60))

    time_match = re.search(r"(\d{3,4})\s*-\s*(\d{3,4})", text)

    if time_match:
        start = time_to_minutes(raw_time_to_hhmm(time_match.group(1)))
        end = time_to_minutes(raw_time_to_hhmm(time_match.group(2)))

        if start is not None and end is not None:
            if end < start:
                end += 24 * 60
            return max(end - start, 0)

    return 0


def extract_shift_range(value: object) -> tuple[str | None, str | None, int | None]:
    if value is None or pd.isna(value):
        return None, None, None

    text = str(value).strip()
    match = re.search(r"(\d{3,4})\s*-\s*(\d{3,4})", text)

    if not match:
        return None, None, None

    start = raw_time_to_hhmm(match.group(1))
    end = raw_time_to_hhmm(match.group(2))

    start_min = time_to_minutes(start)
    end_min = time_to_minutes(end)

    if start_min is None or end_min is None:
        return start, end, None

    if end_min < start_min:
        end_min += 24 * 60

    return start, end, end_min - start_min


def paid_minutes_from_cell(value: object) -> int:
    bracket_minutes = parse_hours_to_minutes(value)

    if bracket_minutes:
        return bracket_minutes

    _, _, elapsed = extract_shift_range(value)

    return int(elapsed or 0)


def contextual_paid_minutes(old_value: object, new_value: object) -> int:
    old_text = "" if old_value is None or pd.isna(old_value) else str(old_value).strip()
    new_text = "" if new_value is None or pd.isna(new_value) else str(new_value).strip()

    old_paid = paid_minutes_from_cell(old_value)
    new_paid = paid_minutes_from_cell(new_value)

    old_start, old_end, old_elapsed = extract_shift_range(old_value)
    new_start, new_end, new_elapsed = extract_shift_range(new_value)

    if new_elapsed is None:
        return new_paid

    old_bracket = parse_hours_to_minutes(old_value)
    new_bracket = parse_hours_to_minutes(new_value)

    range_changed = (old_start, old_end) != (new_start, new_end)
    bracket_same = old_bracket == new_bracket

    if old_elapsed is not None and range_changed and bracket_same and old_text != new_text:
        unpaid_break = max(0, int(old_elapsed) - int(old_paid))
        return max(0, int(new_elapsed) - unpaid_break)

    return new_paid


def refresh_day_hour_brackets(
    edited_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    schema: dict[str, object],
) -> pd.DataFrame:
    out = edited_df.copy().astype("object")
    day_cols: list[str] = list(schema.get("day_cols", []))

    for col in day_cols:
        if col not in out.columns:
            continue

        for idx in out.index:
            old_value = baseline_df.loc[idx, col] if col in baseline_df.columns and idx in baseline_df.index else ""
            new_value = out.loc[idx, col]
            new_text = "" if pd.isna(new_value) else str(new_value).strip()

            if not new_text or extract_shift_range(new_text)[2] is None:
                continue

            minutes = contextual_paid_minutes(old_value, new_value)
            hour_text = f"{minutes // 60:02d}:{minutes % 60:02d}h"

            if re.search(r"\[\s*\d{1,3}\s*:\s*\d{2}\s*h\s*\]", new_text, flags=re.IGNORECASE):
                new_text = re.sub(
                    r"\[\s*\d{1,3}\s*:\s*\d{2}\s*h\s*\]",
                    f"[{hour_text} ]",
                    new_text,
                    flags=re.IGNORECASE,
                )
            else:
                new_text = f"{new_text} [{hour_text} ]"

            out.loc[idx, col] = new_text

    return out


def calculate_weekly_minutes(df: pd.DataFrame, day_cols: list[str]) -> pd.Series:
    if df.empty:
        return pd.Series(dtype="int64")

    total = pd.Series(0, index=df.index, dtype="int64")

    for col in day_cols:
        if col in df.columns:
            total += df[col].apply(parse_hours_to_minutes).astype("int64")

    return total


def calculate_days_off(df: pd.DataFrame, day_cols: list[str]) -> pd.Series:
    if df.empty:
        return pd.Series(dtype="int64")

    total = pd.Series(0, index=df.index, dtype="int64")

    for col in day_cols:
        if col in df.columns:
            total += df[col].apply(lambda v: 1 if is_off_or_empty(v) else 0).astype("int64")

    return total


def update_computed_total_columns(
    df: pd.DataFrame,
    schema: dict[str, object],
    baseline_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    out = df.copy().astype("object")

    day_cols: list[str] = list(schema.get("day_cols", []))
    total_col = schema.get("total_planned")
    days_off_col = schema.get("days_off")

    if baseline_df is not None:
        out = refresh_day_hour_brackets(out, baseline_df, schema)

    if total_col and total_col in out.columns:
        out[total_col] = calculate_weekly_minutes(out, day_cols).apply(minutes_to_hhmm)

    if days_off_col and days_off_col in out.columns:
        out[days_off_col] = calculate_days_off(out, day_cols)

    return out


def parse_shift_cell(value: object) -> dict[str, object]:
    text = "" if value is None or pd.isna(value) else str(value).strip()

    result: dict[str, object] = {
        "raw": text,
        "is_off": is_off_or_empty(value),
        "start": None,
        "end": None,
        "start_min": None,
        "end_min": None,
        "task": "",
        "hours_min": parse_hours_to_minutes(text),
    }

    if result["is_off"]:
        return result

    time_match = re.search(r"(\d{3,4})\s*-\s*(\d{3,4})", text)

    if time_match:
        start = raw_time_to_hhmm(time_match.group(1))
        end = raw_time_to_hhmm(time_match.group(2))

        result.update(
            {
                "start": start,
                "end": end,
                "start_min": time_to_minutes(start),
                "end_min": time_to_minutes(end),
            }
        )

    task_match = re.search(r"\d{3,4}\s*-\s*\d{3,4}\s*\(([^)]+)\)", text)

    if task_match:
        result["task"] = task_match.group(1).strip()
    else:
        code_match = re.match(r"^([A-ZÇĞİÖŞÜ0-9_./-]+)\s*\[", text.upper())

        if code_match:
            candidate = code_match.group(1).strip()

            if not re.fullmatch(r"\d{3,4}-\d{3,4}", candidate):
                result["task"] = candidate

    return result


def full_name(row: pd.Series, schema: dict[str, object]) -> str:
    first_col = schema.get("first_name")
    last_col = schema.get("last_name")

    first = str(row.get(first_col, "") if first_col else "").strip()
    last = str(row.get(last_col, "") if last_col else "").strip()

    return f"{first} {last}".strip()


def task_or_group(task: str, group_value: object) -> str:
    task_text = str(task or "").strip()

    if task_text and not re.fullmatch(r"\d{3,4}-\d{3,4}", task_text):
        return task_text

    group_text = str(group_value or "").strip()

    return group_text or "-"


def get_service_route_overrides() -> dict[str, str]:
    if "service_route_overrides" not in st.session_state:
        st.session_state["service_route_overrides"] = {}

    return st.session_state["service_route_overrides"]


def make_service_override_key(row_id: int, day_col: str, direction: str, time_text: str) -> str:
    return f"{int(row_id)}||{day_col}||{direction}||{time_text}"


def effective_service_code(original_code: object, override_key: str) -> str:
    overrides = get_service_route_overrides()

    if override_key in overrides:
        return str(overrides[override_key]).strip()

    return str(original_code or "").strip()


def build_shift_records(df: pd.DataFrame, schema: dict[str, object]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    # Servis planlama 8 gün dahil tüm günleri kullanır.
    day_cols: list[str] = list(schema.get("service_day_cols", schema.get("day_cols", [])))

    emp_col = schema.get("employee")
    district_col = schema.get("district")
    group_col = schema.get("group")

    for row_index, row in df.iterrows():
        name = full_name(row, schema)
        emp = row.get(emp_col, "") if emp_col else ""
        original_route = row.get(district_col, "") if district_col else ""
        group = row.get(group_col, "") if group_col else ""

        for day_order, day_col in enumerate(day_cols):
            parsed = parse_shift_cell(row.get(day_col, ""))

            if parsed["is_off"]:
                continue

            if not parsed.get("start") and not parsed.get("end"):
                continue

            task_value = task_or_group(str(parsed.get("task", "")), group)

            common = {
                "_row_id": row_index,
                "Employee Number": emp,
                "Ad Soyad": name,
                "First Name": row.get(schema.get("first_name"), "") if schema.get("first_name") else "",
                "Last Name": row.get(schema.get("last_name"), "") if schema.get("last_name") else "",
                "Grup": str(group).strip(),
                "Gün": day_label(str(day_col)),
                "Gün Sütunu": day_order,
                "Gün Kolonu": str(day_col),
                "Vardiya Hücresi": parsed.get("raw", ""),
                "Görev/Uçak Kodu": task_value,
                "Çalışma Saati": minutes_to_hhmm(parsed.get("hours_min", 0)),
                "Orijinal Servis Kodu": str(original_route or "").strip(),
            }

            if parsed.get("start"):
                key = make_service_override_key(row_index, str(day_col), "Geliş", str(parsed["start"]))

                rows.append(
                    {
                        **common,
                        "_override_key": key,
                        "Yön": "Geliş",
                        "Saat": parsed["start"],
                        "Başlangıç": parsed["start"],
                        "Bitiş": parsed.get("end"),
                        "Sıralama Dakika": parsed.get("start_min") or 0,
                        "Servis Kodu": effective_service_code(original_route, key),
                    }
                )

            if parsed.get("end"):
                key = make_service_override_key(row_index, str(day_col), "Gidiş", str(parsed["end"]))

                rows.append(
                    {
                        **common,
                        "_override_key": key,
                        "Yön": "Gidiş",
                        "Saat": parsed["end"],
                        "Başlangıç": parsed.get("start"),
                        "Bitiş": parsed["end"],
                        "Sıralama Dakika": parsed.get("end_min") or 0,
                        "Servis Kodu": effective_service_code(original_route, key),
                    }
                )

    records = pd.DataFrame(rows)

    if not records.empty:
        records = records.sort_values(
            ["Gün Sütunu", "Sıralama Dakika", "Servis Kodu", "Ad Soyad"],
            kind="stable",
        ).reset_index(drop=True)

    return records


def remove_employee_number_columns(df: pd.DataFrame, schema: dict[str, object] | None = None) -> pd.DataFrame:
    out = df.copy()
    possible = {"Employee Number", "Sicil", "Sicil No", "Sicil Numarası"}

    if schema and schema.get("employee"):
        possible.add(str(schema["employee"]))

    for col in list(out.columns):
        if str(col) in possible or str(col).strip().lower() in {"employee number", "sicil"}:
            out = out.drop(columns=[col])

    return out


def drop_internal_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in list(out.columns):
        if str(col).startswith("_") or str(col) in {"Gün Sütunu", "Sıralama Dakika", "Gün Kolonu"}:
            out = out.drop(columns=[col])

    return out


def display_df(df: pd.DataFrame, schema: dict[str, object], hide_employee: bool = False, **kwargs) -> None:
    view = remove_employee_number_columns(df, schema) if hide_employee else df.copy()
    view = drop_internal_columns(view)

    st.dataframe(view, use_container_width=True, hide_index=True, **kwargs)


def add_column_filters(df: pd.DataFrame, key_prefix: str, default_columns: list[str] | None = None) -> pd.DataFrame:
    if df.empty:
        return df

    with st.expander("🔎 Her sütuna göre filtrele", expanded=False):
        cols = list(df.columns)

        selected_cols = st.multiselect(
            "Filtre uygulanacak sütunlar",
            options=cols,
            default=[c for c in (default_columns or []) if c in cols],
            key=f"{key_prefix}_filter_cols",
        )

        filtered = df.copy()

        for col in selected_cols:
            series = filtered[col].fillna("").astype(str)
            unique_values = sorted([x for x in series.unique().tolist() if x != ""])

            if 0 < len(unique_values) <= 80:
                chosen = st.multiselect(col, unique_values, key=f"{key_prefix}_{col}_multi")

                if chosen:
                    filtered = filtered[series.isin(chosen)]
            else:
                text = st.text_input(f"{col} içinde ara", key=f"{key_prefix}_{col}_text")

                if text:
                    filtered = filtered[series.str.contains(text, case=False, na=False, regex=False)]

        return filtered


def build_route_summary(records: pd.DataFrame) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame()

    grouped = (
        records.groupby(
            ["Gün Sütunu", "Gün", "Yön", "Sıralama Dakika", "Saat", "Servis Kodu"],
            dropna=False,
        )
        .agg(
            Personel_Sayısı=("Ad Soyad", "count"),
            Personeller=("Ad Soyad", lambda s: ", ".join(s.astype(str))),
            Görevler=("Görev/Uçak Kodu", lambda s: ", ".join(sorted(set(s.astype(str))))),
        )
        .reset_index()
        .sort_values(["Gün Sütunu", "Sıralama Dakika", "Yön", "Servis Kodu"], kind="stable")
    )

    grouped["Durum"] = grouped["Personel_Sayısı"].apply(lambda x: "⚠️ 4 ve altı" if int(x) <= 4 else "✅ Uygun")
    grouped = grouped.rename(columns={"Personel_Sayısı": "Personel Sayısı"})

    return grouped


def build_transport_table(records: pd.DataFrame, direction: str) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame()

    temp = records[records["Yön"] == direction].copy()

    if temp.empty:
        return pd.DataFrame()

    temp = temp.sort_values(["Gün Sütunu", "Sıralama Dakika", "Servis Kodu", "Ad Soyad"], kind="stable")

    rows: list[dict[str, object]] = []

    for (day_order, day, minute, hour, route), group in temp.groupby(
        ["Gün Sütunu", "Gün", "Sıralama Dakika", "Saat", "Servis Kodu"],
        sort=False,
    ):
        count = len(group)

        rows.append(
            {
                "Satır Tipi": "Başlık",
                "Gün": day,
                "Saat": hour,
                "Servis Kodu": route,
                "Personel Sayısı": count,
                "Durum": "⚠️ 4 ve altı" if count <= 4 else "✅ Uygun",
                "Ad Soyad": "",
                "Görev/Uçak Kodu": "",
                "Grup": "",
                "Vardiya Hücresi": "",
            }
        )

        for _, person in group.iterrows():
            rows.append(
                {
                    "Satır Tipi": "Personel",
                    "Gün": day,
                    "Saat": hour,
                    "Servis Kodu": route,
                    "Personel Sayısı": "",
                    "Durum": "",
                    "Employee Number": person.get("Employee Number", ""),
                    "Ad Soyad": person.get("Ad Soyad", ""),
                    "Görev/Uçak Kodu": person.get("Görev/Uçak Kodu", ""),
                    "Grup": person.get("Grup", ""),
                    "Vardiya Hücresi": person.get("Vardiya Hücresi", ""),
                }
            )

    return pd.DataFrame(rows)


def render_service_route_change_panel(records: pd.DataFrame, schema: dict[str, object], hide_employee: bool = False) -> None:
    st.markdown("#### 🔁 Servis Kodu Değiştir")
    st.caption(
        "Bu işlem sadece seçilen personelin o gün + o saat + geliş/gidiş kaydını değiştirir. "
        "Diğer günleri veya diğer saatleri etkilemez."
    )

    if records.empty:
        st.info("Servis kodu değiştirilecek aktif kayıt bulunamadı.")
        return

    route_options = sorted(
        set(records["Orijinal Servis Kodu"].dropna().astype(str).str.strip())
        | set(records["Servis Kodu"].dropna().astype(str).str.strip())
        | set(get_service_route_overrides().values())
    )
    route_options = [r for r in route_options if r]

    if not route_options:
        st.warning("Servis kodu bulunamadı.")
        return

    edit_df = records[
        [
            "_override_key",
            "Employee Number",
            "Ad Soyad",
            "Gün",
            "Yön",
            "Saat",
            "Servis Kodu",
            "Orijinal Servis Kodu",
            "Görev/Uçak Kodu",
            "Grup",
        ]
    ].copy()

    edit_df = edit_df.drop_duplicates(subset=["_override_key"]).reset_index(drop=True)
    edit_df["Yeni Servis Kodu"] = edit_df["Servis Kodu"].astype(str)

    name_filter = st.text_input(
        "Servis kodu değiştirmek için isim ara",
        placeholder="Örn: Yusuf, Ali, Mehmet",
        key="service_route_name_filter",
    )

    if name_filter:
        edit_df = edit_df[
            edit_df["Ad Soyad"]
            .astype(str)
            .str.contains(name_filter, case=False, na=False, regex=False)
        ].reset_index(drop=True)

    if edit_df.empty:
        st.info("Bu isim filtresine uygun personel bulunamadı.")
        return

    visible_cols = [
        "_override_key",
        "Employee Number",
        "Ad Soyad",
        "Gün",
        "Yön",
        "Saat",
        "Servis Kodu",
        "Yeni Servis Kodu",
        "Görev/Uçak Kodu",
        "Grup",
    ]

    edit_view = edit_df[visible_cols].copy()

    if hide_employee:
        edit_view = edit_view.drop(columns=["Employee Number"], errors="ignore")

    edited = st.data_editor(
        edit_view,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=[c for c in edit_view.columns if c != "Yeni Servis Kodu"],
        column_config={
            "_override_key": None,
            "Yeni Servis Kodu": st.column_config.SelectboxColumn(
                "Yeni Servis Kodu",
                options=route_options,
                required=True,
            ),
        },
        key="service_route_change_editor",
        height=300,
    )

    if st.button("Seçili gün/saat servis değişikliklerini uygula", type="primary"):
        overrides = get_service_route_overrides().copy()
        applied = 0

        for _, row in edited.iterrows():
            key = str(row.get("_override_key", "")).strip()
            new_code = str(row.get("Yeni Servis Kodu", "")).strip()

            if not key or not new_code:
                continue

            original_match = edit_df[edit_df["_override_key"].astype(str) == key]

            if original_match.empty:
                continue

            original_code = str(original_match.iloc[0].get("Orijinal Servis Kodu", "")).strip()
            current_code = str(original_match.iloc[0].get("Servis Kodu", "")).strip()

            if new_code != current_code:
                applied += 1

            if new_code == original_code:
                overrides.pop(key, None)
            else:
                overrides[key] = new_code

        st.session_state["service_route_overrides"] = overrides

        if applied:
            st.success("Servis kodu değiştirildi. Personel sadece seçilen gün ve saatte yeni servis kodu listesine eklendi.")
            st.rerun()
        else:
            st.info("Uygulanacak yeni servis değişikliği bulunamadı.")


def render_dashboard(df: pd.DataFrame, records: pd.DataFrame, schema: dict[str, object], hide_employee: bool = False) -> None:
    st.subheader("📊 Haftalık Özet")

    day_cols: list[str] = list(schema.get("day_cols", []))
    total_minutes = int(calculate_weekly_minutes(df, day_cols).sum()) if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Personel", len(df))
    c2.metric("Aktif Vardiya Kaydı", len(records))
    c3.metric("Toplam Planlanan Saat", minutes_to_hhmm(total_minutes))
    c4.metric("Servis Lokasyonu", records["Servis Kodu"].nunique() if not records.empty else 0)

    if records.empty:
        st.info("Aktif vardiya kaydı bulunamadı.")
        return

    left, right = st.columns([1.3, 1])

    with left:
        st.markdown("#### Saat + Servis Bazlı Yoğunluk")
        summary = build_route_summary(records)
        summary = drop_internal_columns(summary)
        summary = add_column_filters(summary, "dashboard_summary", ["Gün", "Servis Kodu"])
        display_df(summary, schema, hide_employee=hide_employee, height=420)

    with right:
        st.markdown("#### Görev/Uçak Kodu Dağılımı")
        task_summary = (
            records.groupby("Görev/Uçak Kodu")
            .size()
            .reset_index(name="Kayıt Sayısı")
            .sort_values("Kayıt Sayısı", ascending=False)
        )
        st.dataframe(task_summary, use_container_width=True, hide_index=True, height=420)


def render_plan(records: pd.DataFrame, schema: dict[str, object], hide_employee: bool = False) -> None:
    st.subheader("🚌 Kategorize Plan")

    if records.empty:
        st.info("Aktif vardiya bulunamadı.")
        return

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        days = sorted(
            records["Gün"].dropna().unique().tolist(),
            key=lambda x: records.loc[records["Gün"] == x, "Gün Sütunu"].iloc[0],
        )
        selected_days = st.multiselect("Gün", days, default=days, key="plan_days")

    with c2:
        routes = sorted(records["Servis Kodu"].dropna().astype(str).unique().tolist())
        selected_routes = st.multiselect("Servis Kodu", routes, default=[], key="plan_routes")

    with c3:
        tasks = sorted(records["Görev/Uçak Kodu"].dropna().astype(str).unique().tolist())
        selected_tasks = st.multiselect("Görev/Uçak Kodu", tasks, default=[], key="plan_tasks")

    with c4:
        direction = st.selectbox("Liste Tipi", ["Geliş", "Gidiş", "İkisi"], key="plan_direction")

    filtered = records.copy()

    if selected_days:
        filtered = filtered[filtered["Gün"].isin(selected_days)]

    if selected_routes:
        filtered = filtered[filtered["Servis Kodu"].astype(str).isin(selected_routes)]

    if selected_tasks:
        filtered = filtered[filtered["Görev/Uçak Kodu"].astype(str).isin(selected_tasks)]

    if direction != "İkisi":
        filtered_for_change = filtered[filtered["Yön"] == direction].copy()
    else:
        filtered_for_change = filtered.copy()

    st.markdown("#### Detaylı Liste")

    detail_cols = [
        "Employee Number",
        "Ad Soyad",
        "Gün",
        "Yön",
        "Saat",
        "Servis Kodu",
        "Orijinal Servis Kodu",
        "Görev/Uçak Kodu",
        "Çalışma Saati",
        "Vardiya Hücresi",
        "Grup",
    ]

    detail_view = filtered[[c for c in detail_cols if c in filtered.columns]].copy()
    detail_view = add_column_filters(detail_view, "plan_detail", ["Gün", "Servis Kodu", "Görev/Uçak Kodu"])
    display_df(detail_view, schema, hide_employee=hide_employee, height=330)

    render_service_route_change_panel(filtered_for_change, schema, hide_employee=hide_employee)

    st.markdown("#### Haftalık Servis Planlaması")

    tabs = []

    if direction in ["Geliş", "İkisi"]:
        tabs.append("Geliş")

    if direction in ["Gidiş", "İkisi"]:
        tabs.append("Gidiş")

    if len(tabs) == 1:
        table = build_transport_table(filtered, tabs[0])
        table = add_column_filters(table, f"transport_{tabs[0]}", ["Gün", "Saat", "Servis Kodu"])
        display_df(table, schema, hide_employee=hide_employee, height=520)
    else:
        tab_gelis, tab_gidis = st.tabs(["✈️ Geliş", "🏠 Gidiş"])

        with tab_gelis:
            table = build_transport_table(filtered, "Geliş")
            table = add_column_filters(table, "transport_gelis", ["Gün", "Saat", "Servis Kodu"])
            display_df(table, schema, hide_employee=hide_employee, height=520)

        with tab_gidis:
            table = build_transport_table(filtered, "Gidiş")
            table = add_column_filters(table, "transport_gidis", ["Gün", "Saat", "Servis Kodu"])
            display_df(table, schema, hide_employee=hide_employee, height=520)


def changed_day_names(old_df: pd.DataFrame, new_df: pd.DataFrame, schema: dict[str, object], idx: int) -> str:
    names = []

    for col in list(schema.get("day_cols", [])):
        if col not in old_df.columns or col not in new_df.columns:
            continue

        old_val = "" if pd.isna(old_df.loc[idx, col]) else str(old_df.loc[idx, col])
        new_val = "" if pd.isna(new_df.loc[idx, col]) else str(new_df.loc[idx, col])

        if old_val != new_val:
            names.append(day_label(str(col)))

    return ", ".join(names) if names else "-"


def compare_weekly_hours(saved_df: pd.DataFrame, edited_df: pd.DataFrame, schema: dict[str, object]) -> pd.DataFrame:
    day_cols: list[str] = list(schema.get("day_cols", []))

    old_minutes = calculate_weekly_minutes(saved_df, day_cols)
    new_minutes = calculate_weekly_minutes(edited_df, day_cols)

    diff = new_minutes - old_minutes
    changed = diff[diff != 0]

    if changed.empty:
        return pd.DataFrame()

    emp_col = schema.get("employee")

    rows = []

    for idx, value in changed.items():
        rows.append(
            {
                "Sicil": edited_df.loc[idx, emp_col] if emp_col and emp_col in edited_df.columns else "",
                "Ad Soyad": full_name(edited_df.loc[idx], schema),
                "Değişen Gün": changed_day_names(saved_df, edited_df, schema, idx),
                "Eski Haftalık Saat": minutes_to_hhmm(old_minutes.loc[idx]),
                "Yeni Haftalık Saat": minutes_to_hhmm(new_minutes.loc[idx]),
                "Fark": minutes_to_hhmm(value),
            }
        )

    return pd.DataFrame(rows)


def render_roster_editor(schema: dict[str, object], hide_employee: bool = False) -> None:
    st.subheader("✏️ Roster Düzenle")

    active_df = st.session_state["active_roster_df"].copy().astype("object")
    saved_df = st.session_state.get("saved_roster_df", active_df).copy().astype("object")

    first_col = schema.get("first_name")
    search_name = ""

    if first_col and first_col in active_df.columns:
        search_name = st.text_input("First Name / İsim ile ara", placeholder="Örn: Ali, Mehmet, Yusuf")

    editor_df = active_df.copy().astype("object")
    editor_df["_row_id"] = editor_df.index

    # Eğer dosyada 8 gün varsa ilk gün geçmiş hafta kabul edilir.
    # Bu sütun roster düzenlemede gösterilmez ve haftalık saat hesabına girmez.
    excluded_previous_day_col = schema.get("excluded_previous_day_col")

    if excluded_previous_day_col and excluded_previous_day_col in editor_df.columns:
        editor_df = editor_df.drop(columns=[excluded_previous_day_col])

    if search_name and first_col and first_col in editor_df.columns:
        editor_df = editor_df[
            editor_df[first_col]
            .astype(str)
            .str.contains(search_name, case=False, na=False)
        ]

    visible_editor_df = remove_employee_number_columns(editor_df, schema) if hide_employee else editor_df.copy()

    disabled_cols = []

    for col in [schema.get("total_planned"), schema.get("days_off")]:
        if col and col in visible_editor_df.columns:
            disabled_cols.append(col)

    edited_visible = st.data_editor(
        visible_editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=disabled_cols,
        column_config={"_row_id": None},
        key="roster_editor",
        height=520,
    )

    edited_df = edited_visible.copy().astype("object")

    if hide_employee:
        emp_col = schema.get("employee")

        if emp_col and emp_col in active_df.columns and emp_col not in edited_df.columns:
            edited_df[emp_col] = edited_df["_row_id"].apply(lambda rid: active_df.loc[int(rid), emp_col])

        ordered = [c for c in list(active_df.columns) + ["_row_id"] if c in edited_df.columns]
        edited_df = edited_df[ordered]

    row_ids = edited_df["_row_id"].astype(int).tolist()
    baseline_subset = active_df.loc[row_ids].copy().astype("object")
    baseline_subset.index = edited_df.index

    if excluded_previous_day_col and excluded_previous_day_col in baseline_subset.columns:
        baseline_subset_for_editor = baseline_subset.drop(columns=[excluded_previous_day_col])
    else:
        baseline_subset_for_editor = baseline_subset

    computed_edited_df = update_computed_total_columns(
        edited_df,
        schema,
        baseline_df=baseline_subset_for_editor,
    )

    diff_df = compare_weekly_hours(baseline_subset_for_editor, computed_edited_df, schema)

    if not diff_df.empty:
        st.markdown(
            """
            <div class="warning-card">
            ⚠️ Yaptığınız değişiklik haftalık çalışma saatini artırıyor veya azaltıyor. Kaydetmeden önce kontrol edin.
            </div>
            """,
            unsafe_allow_html=True,
        )
        display_df(diff_df, schema, hide_employee=hide_employee)

    preview_cols = [
        schema.get("first_name"),
        schema.get("last_name"),
        schema.get("total_planned"),
        schema.get("days_off"),
    ]
    preview_cols = [c for c in preview_cols if c and c in computed_edited_df.columns]

    if preview_cols:
        st.markdown("#### Otomatik Hesaplanan Toplamlar")
        st.dataframe(computed_edited_df[preview_cols], use_container_width=True, hide_index=True)

    if st.button("Değişiklikleri Kaydet", type="primary"):
        new_active_df = active_df.copy().astype("object")
        save_cols = [c for c in new_active_df.columns if c in computed_edited_df.columns]

        for _, row in computed_edited_df.iterrows():
            row_id = int(row["_row_id"])

            for col in save_cols:
                value = row[col]
                new_active_df.at[row_id, col] = "" if pd.isna(value) else value

        new_active_df = update_computed_total_columns(new_active_df, schema)

        st.session_state["active_roster_df"] = new_active_df.copy().astype("object")
        st.session_state["saved_roster_df"] = new_active_df.copy().astype("object")

        st.success("Roster değişiklikleri kaydedildi.")
        st.rerun()


def build_export_bytes(
    df: pd.DataFrame,
    records: pd.DataFrame,
    schema: dict[str, object],
    hide_employee: bool = False,
) -> bytes:
    buffer = io.BytesIO()

    df_export = remove_employee_number_columns(df, schema) if hide_employee else df.copy()
    records_export = remove_employee_number_columns(records, schema) if hide_employee else records.copy()
    records_export = drop_internal_columns(records_export)

    gelis = build_transport_table(records, "Geliş") if not records.empty else pd.DataFrame()
    gidis = build_transport_table(records, "Gidiş") if not records.empty else pd.DataFrame()

    if hide_employee:
        gelis = remove_employee_number_columns(gelis, schema)
        gidis = remove_employee_number_columns(gidis, schema)

    summary = pd.DataFrame(
        [
            ["Toplam Personel", len(df)],
            ["Aktif Vardiya Kaydı", len(records)],
            [
                "Toplam Planlanan Saat",
                minutes_to_hhmm(calculate_weekly_minutes(df, list(schema.get("day_cols", []))).sum()),
            ],
            ["Servis Lokasyonu", records["Servis Kodu"].nunique() if not records.empty else 0],
        ],
        columns=["Metrik", "Değer"],
    )

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, index=False, sheet_name="Dashboard")
        df_export.to_excel(writer, index=False, sheet_name="Düzenlenen Roster")
        records_export.to_excel(writer, index=False, sheet_name="Ham Vardiya Listesi")
        drop_internal_columns(gelis).to_excel(writer, index=False, sheet_name="Kategorize Geliş")
        drop_internal_columns(gidis).to_excel(writer, index=False, sheet_name="Kategorize Gidiş")

    return buffer.getvalue()


def render_export(df: pd.DataFrame, records: pd.DataFrame, schema: dict[str, object], hide_employee: bool = False) -> None:
    st.subheader("⬇️ Excel Dışa Aktar")

    if hide_employee:
        st.markdown("Planlamacı modunda export alınırken Employee Number / Sicil bilgisi gizlenir.")
    else:
        st.markdown("Roster, ham vardiya listesi, kategorize geliş ve kategorize gidiş sayfalarını tek Excel olarak indirebilirsin.")

    export_bytes = build_export_bytes(df, records, schema, hide_employee=hide_employee)
    file_name = f"celebi_roster_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    st.download_button(
        "📥 Excel olarak indir",
        data=export_bytes,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )


def initialize_from_upload(uploaded_file) -> bool:
    file_bytes = uploaded_file.getvalue()
    file_hash = hash(file_bytes)

    if st.session_state.get("uploaded_hash") == file_hash:
        return True

    try:
        df, sheet_name = read_roster_excel(io.BytesIO(file_bytes))
    except Exception as exc:
        st.error(f"Excel dosyası okunamadı: {exc}")
        return False

    schema = get_schema(df)

    if not schema.get("day_cols"):
        st.error("Gün/vardiya sütunları bulunamadı. Rosterda 6. sütundan itibaren vardiya sütunları olmalı.")
        return False

    df = df.copy().astype("object")
    df = update_computed_total_columns(df, schema)

    st.session_state["uploaded_hash"] = file_hash
    st.session_state["sheet_name"] = sheet_name
    st.session_state["active_roster_df"] = df.copy()
    st.session_state["saved_roster_df"] = df.copy()
    st.session_state["schema"] = schema
    st.session_state["service_route_overrides"] = {}

    return True


def sidebar_upload() -> bool:
    st.sidebar.markdown("## Dosya")
    uploaded_file = st.sidebar.file_uploader("Haftalık roster Excel dosyasını yükle", type=["xlsx"])

    if uploaded_file is None:
        st.sidebar.info("Roster dosyasını yüklediğinde sistem otomatik çalışır.")
        return False

    return initialize_from_upload(uploaded_file)


def main() -> None:
    set_page_style()

    if not require_login():
        return

    logo_header()

    hide_employee = is_planner_mode()

    st.sidebar.markdown(f"### Giriş: {current_role_label()}")

    if hide_employee:
        st.sidebar.caption("Planlamacı modunda Employee Number / Sicil gizlidir.")

    if st.sidebar.button("Çıkış yap"):
        st.session_state.pop("user_role", None)
        st.rerun()

    if not sidebar_upload():
        st.markdown(
            """
            ### Başlamak için roster dosyasını yükle

            Sistem şu mantıkla çalışır:

            1. İlk 5 sütundan personel, servis ve grup bilgilerini alır.
            2. Eğer rosterda 8 gün varsa servis planlama 8 günü de okur.
            3. Roster düzenlemede geçmiş haftanın son günü gösterilmez.
            4. Haftalık çalışma saati sadece yeni haftanın 7 günü üzerinden hesaplanır.
            5. Kategorize Plan ekranında seçilen personelin sadece o gün/saat servis kodunu değiştirebilirsin.
            """
        )
        return

    df: pd.DataFrame = st.session_state["active_roster_df"]
    schema: dict[str, object] = st.session_state["schema"]
    records = build_shift_records(df, schema)

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Okunan sayfa:** `{st.session_state.get('sheet_name', '-')}`")
    st.sidebar.markdown(f"**Personel satırı:** `{len(df)}`")
    st.sidebar.markdown(f"**Aktif vardiya kaydı:** `{len(records)}`")

    if schema.get("excluded_previous_day_col"):
        st.sidebar.markdown(f"**Haftalık saat dışı gün:** `{day_label(str(schema.get('excluded_previous_day_col')))} `")

    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Sayfa",
        ["📊 Dashboard", "🚌 Kategorize Plan", "✏️ Roster Düzenle", "⬇️ Export"],
        index=1,
    )

    if page == "📊 Dashboard":
        render_dashboard(df, records, schema, hide_employee=hide_employee)
    elif page == "🚌 Kategorize Plan":
        render_plan(records, schema, hide_employee=hide_employee)
    elif page == "✏️ Roster Düzenle":
        render_roster_editor(schema, hide_employee=hide_employee)
    else:
        render_export(df, records, schema, hide_employee=hide_employee)


if __name__ == "__main__":
    main()
