from __future__ import annotations

import io
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
ASSET_DIR = APP_DIR / "assets"
# Streamlit Cloud uses an ephemeral filesystem. Exports are generated in memory.

NAVY = "#071A33"
NAVY_2 = "#0B2545"
CARD = "#102A4C"
ACCENT = "#5DD3FF"
TEXT = "#F8FAFC"
MUTED = "#C9D6E8"
WARNING = "#F59E0B"
DANGER = "#EF4444"
SUCCESS = "#22C55E"

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
    "first_name": ["First Name", "İlk Adı", "İsim", "Ad"],
    "last_name": ["Last Name", "Soyadı", "Soyad"],
    "district": ["District", "Servis", "Servis Kodu", "Güzergah", "Guzergah"],
    "group": ["Team or Employee Group", "Grup", "Group"],
    "total_planned": ["Total Planned Working Time", "Toplam Çalışma", "Planlanan Saat"],
    "total_target": ["Total Target Working Time", "Hedef Saat", "Target"],
    "days_off": ["Number of Days off", "Off Gün", "Off Gün Sayısı"],
}

def get_admin_password() -> str:
    """Admin password can be stored in Streamlit Cloud Secrets.

    In Streamlit Cloud, set ADMIN_PASSWORD = "..." under App settings > Secrets.
    A fallback is kept so the app also works immediately after upload.
    """
    try:
        return str(st.secrets.get("ADMIN_PASSWORD", "ayferberat32"))
    except Exception:
        return "ayferberat32"


ROLE_ADMIN = "admin"
ROLE_PLANNER = "planner"



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
        div[data-testid="stMetric"] {{
            background: rgba(16,42,76,.82);
            border: 1px solid rgba(255,255,255,.09);
            padding: 18px 18px 14px 18px;
            border-radius: 18px;
            box-shadow: 0 10px 24px rgba(0,0,0,.22);
        }}
        div[data-testid="stMetricValue"] {{ color: #FFFFFF; }}
        div[data-testid="stMetricLabel"] {{ color: {MUTED}; }}
        .block-container {{ padding-top: 1.3rem; padding-bottom: 2rem; }}
        .hero {{
            background: linear-gradient(90deg, rgba(16,42,76,.95), rgba(7,26,51,.65));
            border: 1px solid rgba(255,255,255,.10);
            border-radius: 24px;
            padding: 22px 24px;
            margin-bottom: 18px;
            box-shadow: 0 14px 32px rgba(0,0,0,.25);
        }}
        .hero h1 {{ margin: 0; font-size: 34px; letter-spacing: .2px; }}
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
        .small-muted {{ color:{MUTED}; font-size: 13px; }}
        .stDataFrame, .stDataEditor {{
            border-radius: 16px;
            overflow: hidden;
        }}
        h1, h2, h3, h4, p, label, span {{ color: inherit; }}
        .warning-card {{
            background: rgba(245, 158, 11, .12);
            border: 1px solid rgba(245, 158, 11, .45);
            color: #FFE9B4;
            border-radius: 18px;
            padding: 16px 18px;
            margin: 10px 0 14px 0;
        }}
        .success-card {{
            background: rgba(34, 197, 94, .12);
            border: 1px solid rgba(34, 197, 94, .35);
            color: #DCFCE7;
            border-radius: 18px;
            padding: 16px 18px;
            margin: 10px 0 14px 0;
        }}
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
                <div><span class="pill">Roster</span><span class="pill">Servis Gruplama</span><span class="pill">Haftalık Saat Kontrolü</span></div>
                <h1>Çelebi Akıllı Roster Planlama Sistemi</h1>
                <p>Haftalık roster Excel’ini yükle; sistem aynı gün, aynı saat ve aynı servis lokasyonundaki personelleri görev kodlarıyla gruplar.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


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


def get_schema(df: pd.DataFrame) -> dict[str, object]:
    cols = [str(c) for c in df.columns]
    schema = {
        "employee": find_col(df, BASE_COLUMN_ALIASES["employee"], 0),
        "first_name": find_col(df, BASE_COLUMN_ALIASES["first_name"], 1),
        "last_name": find_col(df, BASE_COLUMN_ALIASES["last_name"], 2),
        "district": find_col(df, BASE_COLUMN_ALIASES["district"], 3),
        "group": find_col(df, BASE_COLUMN_ALIASES["group"], 4),
        "total_planned": find_col(df, BASE_COLUMN_ALIASES["total_planned"], len(cols) - 3 if len(cols) >= 3 else None),
        "total_target": find_col(df, BASE_COLUMN_ALIASES["total_target"], len(cols) - 2 if len(cols) >= 2 else None),
        "days_off": find_col(df, BASE_COLUMN_ALIASES["days_off"], len(cols) - 1 if len(cols) >= 1 else None),
    }

    day_cols: list[str] = []
    for c in cols:
        if parse_date_column(c) is not None:
            day_cols.append(c)
    if not day_cols and len(cols) >= 12:
        day_cols = cols[5:12]
    schema["day_cols"] = day_cols[:7]
    return schema


def parse_date_column(col: object) -> datetime | None:
    text = normalize_col_name(col)
    m = re.fullmatch(r"(20\d{6})", text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d")
    except ValueError:
        return None


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
    return upper.startswith("DO") or upper in {"OFF", "REST"}


def time_to_minutes(hhmm: str | None) -> int | None:
    if not hhmm:
        return None
    parts = hhmm.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def raw_time_to_hhmm(raw: str) -> str:
    raw = raw.strip().zfill(4)
    return f"{raw[:2]}:{raw[2:]}"


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
        "cross_midnight": False,
    }
    if result["is_off"]:
        return result

    time_match = re.search(r"(\d{3,4})\s*-\s*(\d{3,4})", text)
    if time_match:
        start = raw_time_to_hhmm(time_match.group(1))
        end = raw_time_to_hhmm(time_match.group(2))
        start_min = time_to_minutes(start)
        end_min = time_to_minutes(end)
        result.update({"start": start, "end": end, "start_min": start_min, "end_min": end_min})
        if start_min is not None and end_min is not None and end_min < start_min:
            result["cross_midnight"] = True

    task_match = re.search(r"\d{3,4}\s*-\s*\d{3,4}\s*\(([^)]+)\)", text)
    if task_match:
        result["task"] = task_match.group(1).strip()
    else:
        # Örn: DTO [07:30h] gibi görev kodlarını yakala.
        # Ama 0800-1700 [08:00h] gibi saf vardiya saatlerini görev/uçak kodu sanma.
        code_match = re.match(r"^([A-ZÇĞİÖŞÜ0-9_./-]+)\s*\[", text.upper())
        if code_match:
            candidate = code_match.group(1).strip()
            if not is_shift_time_code(candidate):
                result["task"] = candidate
    return result


def is_shift_time_code(value: object) -> bool:
    """True ise değer görev değil, 0800-1700 gibi vardiya saatidir."""
    if value is None or pd.isna(value):
        return False
    text = str(value).strip()
    return bool(re.fullmatch(r"\d{3,4}\s*-\s*\d{3,4}", text))


def display_task_or_group(task: object, group: object) -> str:
    """Görev alanına yanlışlıkla vardiya saati düştüyse personelin grubunu göster."""
    task_text = "" if task is None or pd.isna(task) else str(task).strip()
    group_text = "" if group is None or pd.isna(group) else str(group).strip()
    if not task_text or task_text == "-" or is_shift_time_code(task_text):
        return group_text or "-"
    return task_text


def parse_hours_to_minutes(value: object) -> int:
    if value is None or pd.isna(value):
        return 0
    text = str(value).strip()
    bracket = re.search(r"\[(\d{1,3})\s*:\s*(\d{2})\s*h", text, re.IGNORECASE)
    if bracket:
        return int(bracket.group(1)) * 60 + int(bracket.group(2))
    direct = re.search(r"(\d{1,3})\s*:\s*(\d{2})\s*h", text, re.IGNORECASE)
    if direct:
        return int(direct.group(1)) * 60 + int(direct.group(2))
    return 0


def minutes_to_hhmm(minutes: int | float | None) -> str:
    if minutes is None:
        return "0:00 h"
    total = int(round(float(minutes)))
    sign = "-" if total < 0 else ""
    total = abs(total)
    return f"{sign}{total // 60}:{total % 60:02d} h"


def split_group(value: object) -> tuple[str, str]:
    if value is None or pd.isna(value):
        return "", ""
    text = str(value)
    group = ""
    team = ""
    gm = re.search(r"Group:\s*([^\-]+)", text, re.IGNORECASE)
    tm = re.search(r"Team:\s*(.+)$", text, re.IGNORECASE)
    if gm:
        group = gm.group(1).strip()
    else:
        group = text.strip()
    if tm:
        team = tm.group(1).strip()
    return group, team


def full_name(row: pd.Series, schema: dict[str, object]) -> str:
    first = row.get(schema["first_name"], "")
    last = row.get(schema["last_name"], "")
    return f"{'' if pd.isna(first) else first} {'' if pd.isna(last) else last}".strip()


def employee_column_candidates(schema: dict[str, object] | None = None) -> set[str]:
    """Columns that contain sicil / employee number information and must be hidden in planner mode."""
    candidates = set(BASE_COLUMN_ALIASES["employee"] + ["Sicil"])
    if schema and schema.get("employee"):
        candidates.add(str(schema.get("employee")))
    return {str(c).strip().lower() for c in candidates if c}


def remove_employee_number_columns(df: pd.DataFrame, schema: dict[str, object] | None = None) -> pd.DataFrame:
    """Return a display/export copy without employee number columns."""
    if df is None or df.empty:
        return df.copy() if isinstance(df, pd.DataFrame) else df
    blocked = employee_column_candidates(schema)
    cols_to_drop = [c for c in df.columns if str(c).strip().lower() in blocked]
    return df.drop(columns=cols_to_drop, errors="ignore").copy()


def current_role_label() -> str:
    role = st.session_state.get("user_role")
    if role == ROLE_ADMIN:
        return "Yönetici"
    if role == ROLE_PLANNER:
        return "Planlamacı"
    return "Giriş Yok"


def is_planner_mode() -> bool:
    return st.session_state.get("user_role") == ROLE_PLANNER


def build_shift_records(df: pd.DataFrame, schema: dict[str, object]) -> pd.DataFrame:
    records = []
    day_cols: list[str] = list(schema["day_cols"])  # type: ignore[arg-type]
    for _, row in df.iterrows():
        emp = row.get(schema["employee"], "")
        first = row.get(schema["first_name"], "")
        last = row.get(schema["last_name"], "")
        route = row.get(schema["district"], "")
        group_raw = row.get(schema["group"], "")
        group, team = split_group(group_raw)
        for day_col in day_cols:
            parsed = parse_shift_cell(row.get(day_col, ""))
            if parsed["is_off"] or not parsed.get("start"):
                continue
            date_value = parse_date_column(day_col)
            start_date = date_value
            end_date = date_value + timedelta(days=1) if date_value and parsed.get("cross_midnight") else date_value
            records.append(
                {
                    "Gün": day_label(day_col),
                    "Tarih": start_date.strftime("%d.%m.%Y") if start_date else str(day_col),
                    "Gidiş Tarihi": end_date.strftime("%d.%m.%Y") if end_date else str(day_col),
                    "Gün Sütunu": day_col,
                    "Sicil": emp,
                    "Ad": first,
                    "Soyad": last,
                    "Ad Soyad": f"{first} {last}".strip(),
                    "Servis Kodu": route,
                    "Grup": group,
                    "Takım": team,
                    "Vardiya": parsed["raw"],
                    "Başlangıç": parsed["start"],
                    "Bitiş": parsed["end"],
                    "Başlangıç Dakika": parsed["start_min"],
                    "Bitiş Dakika": parsed["end_min"],
                    "Görev/Uçak Kodu": display_task_or_group(parsed.get("task", ""), group),
                    "Çalışma Saati": minutes_to_hhmm(parsed["hours_min"]),
                    "Çalışma Dakika": parsed["hours_min"],
                }
            )
    if not records:
        return pd.DataFrame()
    out = pd.DataFrame(records)
    out = out.sort_values(["Gün Sütunu", "Başlangıç Dakika", "Servis Kodu", "Ad Soyad"], kind="stable")
    return out.reset_index(drop=True)


def build_transport_table(records: pd.DataFrame, direction: str) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    if direction == "Geliş":
        sort_cols = ["Gün Sütunu", "Başlangıç Dakika", "Servis Kodu", "Ad Soyad"]
        group_cols = ["Gün Sütunu", "Gün", "Tarih", "Başlangıç", "Servis Kodu"]
        time_col = "Başlangıç"
        date_col = "Tarih"
        direction_text = "To Airport"
    else:
        sort_cols = ["Gün Sütunu", "Bitiş Dakika", "Servis Kodu", "Ad Soyad"]
        group_cols = ["Gün Sütunu", "Gün", "Gidiş Tarihi", "Bitiş", "Servis Kodu"]
        time_col = "Bitiş"
        date_col = "Gidiş Tarihi"
        direction_text = "From Airport"

    temp = records.sort_values(sort_cols, kind="stable")
    for key, group_df in temp.groupby(group_cols, dropna=False, sort=False):
        key_dict = dict(zip(group_cols, key if isinstance(key, tuple) else (key,)))
        header = f"{key_dict.get(date_col)}-{key_dict.get(time_col)}-{direction_text} - {key_dict.get('Servis Kodu')}"
        rows.append(
            {
                "Satır Tipi": "Başlık",
                "Kategori": header,
                "Yön": direction,
                "Tarih": key_dict.get(date_col),
                "Saat": key_dict.get(time_col),
                "Servis Kodu": key_dict.get("Servis Kodu"),
                "Personel Sayısı": len(group_df),
                "Sicil": "",
                "Ad Soyad": "",
                "Görev/Uçak Kodu": "",
                "Vardiya": "",
                "Grup": "",
                "Takım": "",
            }
        )
        for _, person in group_df.iterrows():
            rows.append(
                {
                    "Satır Tipi": "Personel",
                    "Kategori": "",
                    "Yön": direction,
                    "Tarih": key_dict.get(date_col),
                    "Saat": key_dict.get(time_col),
                    "Servis Kodu": key_dict.get("Servis Kodu"),
                    "Personel Sayısı": "",
                    "Sicil": person.get("Sicil", ""),
                    "Ad Soyad": person.get("Ad Soyad", ""),
                    "Görev/Uçak Kodu": person.get("Görev/Uçak Kodu", ""),
                    "Vardiya": person.get("Vardiya", ""),
                    "Grup": person.get("Grup", ""),
                    "Takım": person.get("Takım", ""),
                }
            )
    return pd.DataFrame(rows)


def calculate_weekly_minutes(df: pd.DataFrame, day_cols: list[str]) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=int)
    totals = pd.Series(0, index=df.index, dtype=int)
    for col in day_cols:
        if col in df.columns:
            totals += df[col].apply(parse_hours_to_minutes).astype(int)
    return totals


def extract_shift_range(value: object) -> tuple[int | None, int | None, int | None]:
    """Return start, end and elapsed minutes from a roster cell such as 0800-1700 [08:00h]."""
    if value is None or pd.isna(value):
        return None, None, None
    text = str(value).strip()
    match = re.search(r"(\d{3,4})\s*-\s*(\d{3,4})", text)
    if not match:
        return None, None, None
    start = time_to_minutes(raw_time_to_hhmm(match.group(1)))
    end = time_to_minutes(raw_time_to_hhmm(match.group(2)))
    if start is None or end is None:
        return None, None, None
    elapsed = end - start
    if elapsed < 0:
        elapsed += 24 * 60
    return start, end, elapsed


def paid_minutes_from_cell(value: object) -> int:
    """Normal paid minutes. Bracket hours are trusted; if missing, fall back to shift duration."""
    bracket_minutes = parse_hours_to_minutes(value)
    if bracket_minutes:
        return bracket_minutes
    _, _, elapsed = extract_shift_range(value)
    return int(elapsed or 0)


def contextual_paid_minutes(old_value: object, new_value: object) -> int:
    """
    Calculate edited paid minutes even when the user changes only 0800-1700 part
    and forgets to update [08:00h]. We keep the old unpaid break amount stable.
    Example: 0800-1700 [08:00h] -> 0900-1700 [08:00h] becomes 07:00h.
    """
    old_text = "" if old_value is None or pd.isna(old_value) else str(old_value).strip()
    new_text = "" if new_value is None or pd.isna(new_value) else str(new_value).strip()

    old_paid = paid_minutes_from_cell(old_value)
    new_paid = paid_minutes_from_cell(new_value)
    old_start, old_end, old_elapsed = extract_shift_range(old_value)
    new_start, new_end, new_elapsed = extract_shift_range(new_value)

    # If no time range exists in the new cell, bracket/off values are the only reliable signal.
    if new_elapsed is None:
        return new_paid

    # When only the visible start/end hour changes but the bracket stays the same,
    # Streamlit used to miss the weekly-hour difference. Adjust from the old break logic.
    old_bracket = parse_hours_to_minutes(old_value)
    new_bracket = parse_hours_to_minutes(new_value)
    range_changed = (old_start, old_end) != (new_start, new_end)
    bracket_same = old_bracket == new_bracket

    if old_elapsed is not None and range_changed and bracket_same and old_text != new_text:
        unpaid_break = max(0, int(old_elapsed) - int(old_paid))
        return max(0, int(new_elapsed) - unpaid_break)

    return new_paid


def calculate_weekly_minutes_contextual(saved_df: pd.DataFrame, edited_df: pd.DataFrame, day_cols: list[str]) -> tuple[pd.Series, pd.Series]:
    old_totals = pd.Series(0, index=edited_df.index, dtype=int)
    new_totals = pd.Series(0, index=edited_df.index, dtype=int)
    for col in day_cols:
        if col not in edited_df.columns:
            continue
        old_col = saved_df[col] if col in saved_df.columns else pd.Series("", index=edited_df.index)
        for idx in edited_df.index:
            old_value = old_col.loc[idx] if idx in old_col.index else ""
            new_value = edited_df.loc[idx, col]
            old_totals.loc[idx] += paid_minutes_from_cell(old_value)
            new_totals.loc[idx] += contextual_paid_minutes(old_value, new_value)
    return old_totals, new_totals


def changed_day_names(saved_df: pd.DataFrame, edited_df: pd.DataFrame, schema: dict[str, object], row_index: int) -> str:
    day_cols: list[str] = list(schema["day_cols"])  # type: ignore[arg-type]
    changed = []
    for col in day_cols:
        if col not in saved_df.columns or col not in edited_df.columns:
            continue
        old_value = "" if pd.isna(saved_df.loc[row_index, col]) else str(saved_df.loc[row_index, col]).strip()
        new_value = "" if pd.isna(edited_df.loc[row_index, col]) else str(edited_df.loc[row_index, col]).strip()
        if old_value != new_value:
            changed.append(day_label(col))
    return ", ".join(changed)


def refresh_day_hour_brackets(edited_df: pd.DataFrame, baseline_df: pd.DataFrame, schema: dict[str, object]) -> pd.DataFrame:
    """Update [HH:MMh] parts after edited start/end times so later reports use the new hours."""
    out = edited_df.copy()
    day_cols: list[str] = list(schema["day_cols"])  # type: ignore[arg-type]
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
                new_text = re.sub(r"\[\s*\d{1,3}\s*:\s*\d{2}\s*h\s*\]", f"[{hour_text} ]", new_text, flags=re.IGNORECASE)
            else:
                new_text = f"{new_text} [{hour_text} ]"
            out.loc[idx, col] = new_text
    return out


def calculate_days_off(df: pd.DataFrame, day_cols: list[str]) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=int)
    totals = pd.Series(0, index=df.index, dtype=int)
    for col in day_cols:
        if col in df.columns:
            totals += df[col].apply(lambda x: 1 if is_off_or_empty(x) else 0).astype(int)
    return totals


def compare_weekly_hours(saved_df: pd.DataFrame, edited_df: pd.DataFrame, schema: dict[str, object]) -> pd.DataFrame:
    day_cols: list[str] = list(schema["day_cols"])  # type: ignore[arg-type]
    # Total Planned Working Time mantığı: Pazartesi-Pazar hücrelerindeki
    # köşeli parantez [] içinde yazan saatler toplanır.
    old_minutes = calculate_weekly_minutes(saved_df, day_cols)
    new_minutes = calculate_weekly_minutes(edited_df, day_cols)
    diff = new_minutes - old_minutes
    mask = diff != 0
    if not mask.any():
        return pd.DataFrame()
    emp_col = schema["employee"]
    rows = []
    for idx in diff[mask].index:
        rows.append(
            {
                "Sicil": edited_df.loc[idx, emp_col] if emp_col in edited_df.columns else "",
                "Ad Soyad": full_name(edited_df.loc[idx], schema),
                "Değişen Gün": changed_day_names(saved_df, edited_df, schema, idx),
                "Eski Haftalık Saat": minutes_to_hhmm(old_minutes.loc[idx]),
                "Yeni Haftalık Saat": minutes_to_hhmm(new_minutes.loc[idx]),
                "Fark": minutes_to_hhmm(diff.loc[idx]),
            }
        )
    return pd.DataFrame(rows)


def update_computed_total_columns(df: pd.DataFrame, schema: dict[str, object], baseline_df: pd.DataFrame | None = None) -> pd.DataFrame:
    out = df.copy()
    day_cols: list[str] = list(schema["day_cols"])  # type: ignore[arg-type]
    total_col = schema.get("total_planned")
    days_off_col = schema.get("days_off")
    if baseline_df is not None:
        out = refresh_day_hour_brackets(out, baseline_df, schema)
    if total_col and total_col in out.columns:
        # Total Planned Working Time her zaman gün hücrelerindeki [] içi
        # saatlerin toplamıdır. Kullanıcı [08:00h] değerini [09:00h]
        # yaparsa toplam da doğrudan buna göre güncellenir.
        out[total_col] = calculate_weekly_minutes(out, day_cols).apply(minutes_to_hhmm)
    if days_off_col and days_off_col in out.columns:
        out[days_off_col] = calculate_days_off(out, day_cols)
    return out


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


def kpi_row(df: pd.DataFrame, records: pd.DataFrame, schema: dict[str, object]) -> None:
    day_cols: list[str] = list(schema["day_cols"])  # type: ignore[arg-type]
    total_staff = len(df)
    active_shift_count = len(records)
    total_hours_min = int(calculate_weekly_minutes(df, day_cols).sum()) if not df.empty else 0
    route_count = records["Servis Kodu"].nunique() if not records.empty else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Personel", f"{total_staff:,}".replace(",", "."))
    c2.metric("Haftalık Aktif Vardiya Kaydı", f"{active_shift_count:,}".replace(",", "."))
    c3.metric("Toplam Planlanan Saat", minutes_to_hhmm(total_hours_min))
    c4.metric("Servis Lokasyonu", f"{route_count:,}".replace(",", "."))


def render_dashboard(df: pd.DataFrame, records: pd.DataFrame, schema: dict[str, object], hide_employee: bool = False) -> None:
    st.subheader("📊 Haftalık Özet")
    kpi_row(df, records, schema)
    st.write("")

    if records.empty:
        st.info("Aktif vardiya kaydı bulunamadı. Roster formatını kontrol edin.")
        return

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("#### Saat + Servis Bazlı Yoğunluk")
        summary = (
            records.groupby(["Gün Sütunu", "Gün", "Başlangıç Dakika", "Başlangıç", "Servis Kodu"], dropna=False)
            .size()
            .reset_index(name="Personel Sayısı")
            .sort_values(["Gün Sütunu", "Başlangıç Dakika", "Servis Kodu"], kind="stable")
        )
        summary = summary.drop(columns=["Gün Sütunu", "Başlangıç Dakika"], errors="ignore")
        filtered = add_column_filters(summary, "dashboard_summary", ["Gün", "Servis Kodu"])
        st.dataframe(filtered, use_container_width=True, hide_index=True)
    with right:
        st.markdown("#### Görev/Uçak Kodu Dağılımı")
        task_summary = records.groupby("Görev/Uçak Kodu").size().reset_index(name="Kayıt Sayısı").sort_values("Kayıt Sayısı", ascending=False)
        st.dataframe(task_summary, use_container_width=True, hide_index=True)


def render_plan(records: pd.DataFrame, schema: dict[str, object], hide_employee: bool = False) -> None:
    st.subheader("🚌 Kategorize Servis Planı")
    if records.empty:
        st.info("Aktif vardiya bulunamadı.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        days = sorted(records["Gün"].dropna().unique().tolist(), key=lambda x: records.loc[records["Gün"] == x, "Gün Sütunu"].iloc[0])
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

    st.markdown("#### Detaylı Liste")
    detail_cols = [
        "Gün", "Tarih", "Sicil", "Ad Soyad", "Servis Kodu", "Başlangıç", "Bitiş",
        "Görev/Uçak Kodu", "Çalışma Saati", "Vardiya", "Grup", "Takım"
    ]
    detail_view = filtered[[c for c in detail_cols if c in filtered.columns]]
    if hide_employee:
        detail_view = remove_employee_number_columns(detail_view, schema)
    detail_view = add_column_filters(detail_view, "plan_detail", ["Gün", "Servis Kodu", "Görev/Uçak Kodu"])
    st.dataframe(detail_view, use_container_width=True, hide_index=True, height=360)

    st.markdown("#### Haftalık Servis Planlaması")
    tabs = []
    if direction in ["Geliş", "İkisi"]:
        tabs.append("Geliş")
    if direction in ["Gidiş", "İkisi"]:
        tabs.append("Gidiş")

    if len(tabs) == 1:
        table = build_transport_table(filtered, tabs[0])
        if hide_employee:
            table = remove_employee_number_columns(table, schema)
        table = add_column_filters(table, f"transport_{tabs[0]}", ["Tarih", "Saat", "Servis Kodu"])
        st.dataframe(table, use_container_width=True, hide_index=True, height=520)
    else:
        tab_gelis, tab_gidis = st.tabs(["✈️ Geliş / To Airport", "🏠 Gidiş / From Airport"])
        with tab_gelis:
            table = build_transport_table(filtered, "Geliş")
            if hide_employee:
                table = remove_employee_number_columns(table, schema)
            table = add_column_filters(table, "transport_gelis", ["Tarih", "Saat", "Servis Kodu"])
            st.dataframe(table, use_container_width=True, hide_index=True, height=520)
        with tab_gidis:
            table = build_transport_table(filtered, "Gidiş")
            if hide_employee:
                table = remove_employee_number_columns(table, schema)
            table = add_column_filters(table, "transport_gidis", ["Tarih", "Saat", "Servis Kodu"])
            st.dataframe(table, use_container_width=True, hide_index=True, height=520)


def render_roster_editor(schema: dict[str, object], hide_employee: bool = False) -> None:
    st.subheader("✏️ Roster Düzenle")
    st.markdown(
        "<p class='small-muted'>Bu sayfada yüklediğin roster aynı tablo mantığıyla durur. Günlük vardiya hücrelerinde değişiklik yaparsan sistem haftalık saatin artıp azaldığını kontrol eder.</p>",
        unsafe_allow_html=True,
    )
    raw_active_df: pd.DataFrame = st.session_state["active_roster_df"]
    raw_saved_df: pd.DataFrame = st.session_state["saved_roster_df"]
    day_cols: list[str] = list(schema["day_cols"])  # type: ignore[arg-type]

    # Streamlit data_editor'da TextColumn kullanınca, Excel'den sayı gelen
    # sicil/total gibi sütunlar önce metne çevrilmezse ColumnDataKind hatası verir.
    # Bu yüzden editöre verilen kopyayı tamamen metin uyumlu hale getiriyoruz.
    active_df = raw_active_df.copy()
    saved_df = raw_saved_df.copy()
    for col in active_df.columns:
        active_df[col] = active_df[col].apply(lambda v: "" if pd.isna(v) else str(v))
    for col in saved_df.columns:
        saved_df[col] = saved_df[col].apply(lambda v: "" if pd.isna(v) else str(v))

    first_name_col = schema.get("first_name")
    search_name = ""
    if first_name_col and first_name_col in active_df.columns:
        search_name = st.text_input(
            "First Name / İsim ile ara",
            placeholder="Örn: Ali, Mehmet, Yusuf...",
            key="roster_first_name_search",
        ).strip()
    else:
        st.info("First Name sütunu bulunamadığı için isim araması gösterilemiyor.")

    editor_df = active_df.copy()
    saved_editor_df = saved_df.copy()
    if search_name and first_name_col and first_name_col in editor_df.columns:
        name_mask = editor_df[first_name_col].astype(str).str.contains(search_name, case=False, na=False, regex=False)
        editor_df = editor_df.loc[name_mask].copy()
        saved_editor_df = saved_editor_df.loc[editor_df.index].copy()
        st.caption(f"{len(editor_df)} personel listeleniyor. Arama temizlenirse tüm roster görünür.")
        if editor_df.empty:
            st.warning("Bu isimle eşleşen personel bulunamadı.")

    if hide_employee:
        editor_df = remove_employee_number_columns(editor_df, schema)
        saved_editor_df = remove_employee_number_columns(saved_editor_df, schema)
        st.caption("Planlamacı modunda Employee Number / Sicil bilgisi gizlidir.")

    # Total Working Time ve Off Gün Sayısı artık manuel alan değil; Pazartesi-Pazar
    # hücrelerindeki [HH:MMh] bilgilerine göre otomatik hesaplanır.
    total_col = schema.get("total_planned")
    days_off_col = schema.get("days_off")
    computed_cols = [c for c in [total_col, days_off_col] if c and c in active_df.columns]

    column_config = {}
    for col in editor_df.columns:
        label = day_label(col) if col in day_cols else col
        help_text = None
        if col == total_col:
            help_text = "Pazartesi-Pazar vardiya hücrelerindeki [HH:MMh] değerlerinin otomatik toplamıdır."
        elif col == days_off_col:
            help_text = "Pazartesi-Pazar içinde OFF/DO/boş günlerin otomatik sayımıdır."
        column_config[col] = st.column_config.TextColumn(label=label, width="medium", help=help_text)

    edited_df = st.data_editor(
        editor_df,
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        height=560,
        column_config=column_config,
        disabled=[c for c in computed_cols if c in editor_df.columns],
        key="roster_editor",
    )

    # Editörün döndürdüğü tablo üzerinden yeni saatleri hemen hesapla. Böylece
    # kullanıcı 0800-1700 [08:00h] değerini 0900-1700 olarak değiştirirse
    # bracket ve Total Working Time kayıtta otomatik güncellenir.
    computed_edited_df = update_computed_total_columns(edited_df, schema, saved_editor_df)

    # Canlı önizleme: Streamlit data_editor aynı render içinde hesaplanan hücreyi
    # görsel olarak değiştiremeyebilir; bu tablo kaydedilecek yeni total değerini net gösterir.
    changed_total_preview = compare_weekly_hours(saved_editor_df, computed_edited_df, schema)
    if total_col and total_col in computed_edited_df.columns and not changed_total_preview.empty:
        preview_new_minutes = calculate_weekly_minutes(computed_edited_df, day_cols)
        preview_old_minutes = calculate_weekly_minutes(saved_editor_df, day_cols)
        preview_indices = preview_new_minutes[preview_new_minutes != preview_old_minutes].index.tolist()
        preview_cols = [c for c in [schema.get("employee"), schema.get("first_name"), schema.get("last_name"), total_col, days_off_col] if c and c in computed_edited_df.columns]
        preview_df = computed_edited_df.loc[preview_indices, preview_cols]
        if hide_employee:
            preview_df = remove_employee_number_columns(preview_df, schema)
        st.markdown("#### 🔄 Otomatik Total Working Time Önizlemesi")
        st.caption("Aşağıdaki değerler Pazartesi-Pazar hücrelerindeki [] içi saatlerin toplamına göre kaydedilecek yeni değerlerdir.")
        st.dataframe(preview_df, use_container_width=True, hide_index=True)

    diffs = changed_total_preview
    if not diffs.empty:
        st.markdown(
            """
            <div class="warning-card">
            ⚠️ <b>Yaptığınız değişiklik haftalık çalışma saatini değiştiriyor.</b><br>
            Aşağıdaki personellerde yeni haftalık saat oluşuyor. Eminseniz değişikliği aktif listeye kaydedin.
            </div>
            """,
            unsafe_allow_html=True,
        )
        display_diffs = remove_employee_number_columns(diffs, schema) if hide_employee else diffs
        st.dataframe(display_diffs, use_container_width=True, hide_index=True)
        if st.button("✅ Evet, değişikliği aktif listeye kaydet", type="primary"):
            # Streamlit Cloud / Pandas 3 + Arrow string uyumluluğu:
            # .loc ile Arrow string sütunlarına DataFrame toplu atama TypeError verebildiği için
            # kayıt öncesi tüm tabloyu normal Python object tipine çeviriyoruz.
            computed_to_save = computed_edited_df.copy().astype("object").where(pd.notna(computed_edited_df), "")
            new_active_df = active_df.copy().astype("object")
            new_saved_df = saved_df.copy().astype("object")
            new_active_df.loc[computed_to_save.index, computed_to_save.columns] = computed_to_save
            new_saved_df.loc[computed_to_save.index, computed_to_save.columns] = computed_to_save
            st.session_state["active_roster_df"] = new_active_df.copy()
            st.session_state["saved_roster_df"] = new_saved_df.copy()
            st.markdown("<div class='success-card'>Değişiklikler aktif listeye kaydedildi. Total Working Time otomatik güncellendi.</div>", unsafe_allow_html=True)
            st.rerun()
    else:
        if not computed_edited_df.equals(saved_editor_df):
            if st.button("✅ Değişiklikleri aktif listeye kaydet", type="primary"):
                # Streamlit Cloud / Pandas 3 + Arrow string uyumluluğu:
                # .loc ile Arrow string sütunlarına DataFrame toplu atama TypeError verebildiği için
                # kayıt öncesi tüm tabloyu normal Python object tipine çeviriyoruz.
                computed_to_save = computed_edited_df.copy().astype("object").where(pd.notna(computed_edited_df), "")
                new_active_df = active_df.copy().astype("object")
                new_saved_df = saved_df.copy().astype("object")
                new_active_df.loc[computed_to_save.index, computed_to_save.columns] = computed_to_save
                new_saved_df.loc[computed_to_save.index, computed_to_save.columns] = computed_to_save
                st.session_state["active_roster_df"] = new_active_df.copy()
                st.session_state["saved_roster_df"] = new_saved_df.copy()
                st.success("Değişiklikler kaydedildi. Total Working Time otomatik güncellendi.")
                st.rerun()
        else:
            st.info("Şu anda haftalık saati değiştiren bir düzenleme yok.")

    st.markdown("#### Filtreli Roster Görüntüleme")
    view_df = computed_edited_df.copy()
    if hide_employee:
        view_df = remove_employee_number_columns(view_df, schema)
    view_df = add_column_filters(view_df, "roster_view", [schema["first_name"], schema["district"], schema["group"]])
    st.dataframe(view_df, use_container_width=True, hide_index=True, height=380)


def build_export_bytes(df: pd.DataFrame, records: pd.DataFrame, schema: dict[str, object], hide_employee: bool = False) -> bytes:
    buffer = io.BytesIO()
    df_export = remove_employee_number_columns(df, schema) if hide_employee else df.copy()
    records_export = remove_employee_number_columns(records, schema) if hide_employee else records.copy()
    gelis = build_transport_table(records, "Geliş") if not records.empty else pd.DataFrame()
    gidis = build_transport_table(records, "Gidiş") if not records.empty else pd.DataFrame()
    if hide_employee:
        gelis = remove_employee_number_columns(gelis, schema)
        gidis = remove_employee_number_columns(gidis, schema)
    summary = pd.DataFrame(
        [
            ["Toplam Personel", len(df)],
            ["Aktif Vardiya Kaydı", len(records)],
            ["Toplam Planlanan Saat", minutes_to_hhmm(calculate_weekly_minutes(df, list(schema["day_cols"])).sum())],
            ["Servis Lokasyonu", records["Servis Kodu"].nunique() if not records.empty else 0],
        ],
        columns=["Metrik", "Değer"],
    )
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        summary.to_excel(writer, index=False, sheet_name="Dashboard")
        df_export.to_excel(writer, index=False, sheet_name="Düzenlenen Roster")
        records_export.to_excel(writer, index=False, sheet_name="Ham Vardiya Listesi")
        gelis.to_excel(writer, index=False, sheet_name="Kategorize Geliş")
        gidis.to_excel(writer, index=False, sheet_name="Kategorize Gidiş")

        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": NAVY_2, "border": 1})
        title_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": NAVY, "font_size": 14})
        cell_fmt = workbook.add_format({"border": 1})
        header_row_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#123B66", "border": 1})
        person_row_fmt = workbook.add_format({"border": 1})
        for sheet_name, dataframe in {
            "Dashboard": summary,
            "Düzenlenen Roster": df_export,
            "Ham Vardiya Listesi": records_export,
            "Kategorize Geliş": gelis,
            "Kategorize Gidiş": gidis,
        }.items():
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            ws.set_tab_color(NAVY_2)
            if not dataframe.empty:
                for col_num, col_name in enumerate(dataframe.columns):
                    ws.write(0, col_num, col_name, header_fmt)
                    width = min(max(len(str(col_name)) + 4, 12), 34)
                    try:
                        sample_width = int(dataframe[col_name].astype(str).head(80).map(len).max()) + 2
                        width = min(max(width, sample_width), 42)
                    except Exception:
                        pass
                    ws.set_column(col_num, col_num, width, cell_fmt)
                last_row = len(dataframe)
                last_col = max(len(dataframe.columns) - 1, 0)
                ws.autofilter(0, 0, last_row, last_col)
                if sheet_name.startswith("Kategorize") and "Satır Tipi" in dataframe.columns:
                    type_col = dataframe.columns.get_loc("Satır Tipi")
                    for excel_row, row_type in enumerate(dataframe["Satır Tipi"].tolist(), start=1):
                        fmt = header_row_fmt if row_type == "Başlık" else person_row_fmt
                        ws.set_row(excel_row, None, fmt)
            if sheet_name == "Dashboard":
                ws.merge_range("D1:H1", "Çelebi Roster Planlama Sistemi", title_fmt)
    return buffer.getvalue()


def render_export(df: pd.DataFrame, records: pd.DataFrame, schema: dict[str, object], hide_employee: bool = False) -> None:
    st.subheader("⬇️ Excel Dışa Aktar")
    if hide_employee:
        st.markdown("Planlamacı modunda export alınırken Employee Number / Sicil bilgisi de gizlenir.")
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
    st.markdown("#### Export içinde oluşan sayfalar")
    st.write("Dashboard · Düzenlenen Roster · Ham Vardiya Listesi · Kategorize Geliş · Kategorize Gidiş")


def render_login_page() -> bool:
    logo_path = ASSET_DIR / "celebi_logo.svg"
    top_left, top_right = st.columns([1, 5])
    with top_left:
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        else:
            st.markdown("### ÇELEBİ")
    with top_right:
        st.markdown(
            """
            <div class="hero">
                <div><span class="pill">Yönetici</span><span class="pill">Planlamacı</span><span class="pill">Gizli Sicil Modu</span></div>
                <h1>Çelebi Roster Planlama Girişi</h1>
                <p>Yönetici modunda tüm bilgiler görünür. Planlamacı modunda Employee Number / Sicil hiçbir ekranda gösterilmez.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    admin_col, planner_col = st.columns(2)
    with admin_col:
        st.markdown("### 🔐 Yönetici Girişi")
        admin_password = st.text_input("Yönetici şifresi", type="password", key="admin_password_input")
        if st.button("Yönetici olarak giriş yap", type="primary", use_container_width=True):
            if admin_password == get_admin_password():
                st.session_state["user_role"] = ROLE_ADMIN
                st.success("Yönetici girişi başarılı.")
                st.rerun()
            else:
                st.error("Yönetici şifresi hatalı.")

    with planner_col:
        st.markdown("### 🧭 Planlamacı Girişi")
        st.caption("Bu girişte şifre yoktur. Employee Number / Sicil alanları tüm ekranlarda ve exportta gizlenir.")
        if st.button("Planlamacı olarak giriş yap", use_container_width=True):
            st.session_state["user_role"] = ROLE_PLANNER
            st.success("Planlamacı girişi başarılı.")
            st.rerun()

    return False


def require_login() -> bool:
    if st.session_state.get("user_role") in {ROLE_ADMIN, ROLE_PLANNER}:
        return True
    return render_login_page()


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
        st.error("Gün/vardiya sütunları bulunamadı. Rosterda 6. sütundan itibaren 7 günlük vardiya sütunu olmalı.")
        return False
    st.session_state["uploaded_hash"] = file_hash
    st.session_state["sheet_name"] = sheet_name
    st.session_state["active_roster_df"] = df.copy()
    st.session_state["saved_roster_df"] = df.copy()
    st.session_state["schema"] = schema
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
            1. İlk 5 sütundan personel ve servis bilgilerini alır.
            2. 6. sütundan itibaren Pazartesi–Pazar vardiya hücrelerini okur.
            3. Aynı gün + aynı saat + aynı servis kodundaki personeli gruplar.
            4. Personelin yanında görev/uçak kodunu gösterir.
            5. Roster düzenlemede haftalık saat değişirse uyarı verir.
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
