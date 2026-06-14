import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from io import BytesIO
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


st.set_page_config(page_title="대학생 월별 예산 관리 앱", layout="wide")
st.title("대학생 맞춤형 월별 예산 관리 웹앱")


# -----------------------------
# 세션 상태 초기화
# -----------------------------
if "income_data" not in st.session_state:
    st.session_state.income_data = {}

if "expense_data" not in st.session_state:
    st.session_state.expense_data = {}

if "expense_records" not in st.session_state:
    st.session_state.expense_records = []

if "saving_goal" not in st.session_state:
    st.session_state.saving_goal = 0


# -----------------------------
# 함수
# -----------------------------
def update_expense_summary():
    if len(st.session_state.expense_records) == 0:
        st.session_state.expense_data = {}
        return

    expense_df = pd.DataFrame(st.session_state.expense_records)
    category_sum = expense_df.groupby("항목")["금액"].sum().to_dict()

    categories = ["식비", "카페/간식", "교통비", "쇼핑", "여가/문화", "고정지출", "기타 지출"]

    st.session_state.expense_data = {
        category: int(category_sum.get(category, 0)) for category in categories
    }


def search_scholarships(keyword, max_results=10):
    query = quote(keyword)
    url = f"https://search.naver.com/search.naver?query={query}"

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
    except Exception as e:
        return pd.DataFrame([{
            "제목": "검색 실패",
            "요약": str(e),
            "링크": ""
        }])

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        link = a["href"]

        if not title:
            continue

        if "장학" in title or "장학생" in title or "국가장학금" in title:
            results.append({
                "제목": title,
                "요약": "검색 결과에서 수집된 장학금 관련 항목입니다.",
                "링크": link
            })

        if len(results) >= max_results:
            break

    if len(results) == 0:
        return pd.DataFrame([{
            "제목": "검색 결과 없음",
            "요약": "조건에 맞는 장학금 검색 결과를 찾지 못했습니다.",
            "링크": ""
        }])

    return pd.DataFrame(results)


def search_discounts(keyword, max_results=10):
    query = quote(keyword)
    url = f"https://search.naver.com/search.naver?query={query}"

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
    except Exception as e:
        return pd.DataFrame([{
            "제목": "검색 실패",
            "요약": str(e),
            "링크": ""
        }])

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        link = a["href"]

        if not title:
            continue

        if "할인" in title or "세일" in title or "쿠폰" in title or "이벤트" in title:
            results.append({
                "제목": title,
                "요약": "검색 결과에서 수집된 할인 관련 정보입니다.",
                "링크": link
            })

        if len(results) >= max_results:
            break

    if len(results) == 0:
        return pd.DataFrame([{
            "제목": "검색 결과 없음",
            "요약": "조건에 맞는 할인 정보를 찾지 못했습니다.",
            "링크": ""
        }])

    return pd.DataFrame(results)


def get_budget_status(total_income, total_expense):
    if total_income == 0:
        return "수입 정보 없음", 0

    rate = total_expense / total_income * 100

    if rate < 70:
        return "안정", rate
    elif rate < 90:
        return "주의", rate
    elif rate <= 100:
        return "위험", rate
    else:
        return "초과", rate


def get_consumption_type():
    expense_data = st.session_state.expense_data

    if len(expense_data) == 0 or sum(expense_data.values()) == 0:
        return "지출 정보 없음", "먼저 지출 정보를 입력해야 소비 유형을 진단할 수 있습니다."

    max_category = max(expense_data, key=expense_data.get)

    advice_map = {
        "식비": "식비 집중형: 외식 횟수를 줄이고 학식이나 도시락을 활용하면 좋습니다.",
        "카페/간식": "소소한 지출 누적형: 카페와 간식처럼 작은 소비가 반복되어 지출이 커지고 있습니다.",
        "교통비": "이동 비용 부담형: 정기권, 도보 이동, 자전거 이용 등을 고려해볼 수 있습니다.",
        "쇼핑": "쇼핑 소비형: 구매 전 필요한 물건인지 확인하고 예산 한도를 정해두는 것이 좋습니다.",
        "여가/문화": "여가 중심형: 무료 전시, 학교 행사, 할인 혜택을 활용하면 좋습니다.",
        "고정지출": "고정비 부담형: 통신비, 구독 서비스 등 반복 지출을 점검해보세요.",
        "기타 지출": "기타 지출 관리 필요형: 세부 항목을 나누어 기록하면 더 정확한 분석이 가능합니다."
    }

    return max_category, advice_map.get(max_category, "소비 유형을 분석했습니다.")


def create_pdf_report():
    buffer = BytesIO()

    try:
        pdfmetrics.registerFont(TTFont("KoreanFont", "C:/Windows/Fonts/malgun.ttf"))
        font_name = "KoreanFont"
    except:
        font_name = "Helvetica"

    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=18,
        leading=24
    )

    normal_style = ParagraphStyle(
        "NormalStyle",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=11,
        leading=16
    )

    elements = []

    total_income = sum(st.session_state.income_data.values())
    total_expense = sum(st.session_state.expense_data.values())
    saving_goal = st.session_state.saving_goal
    remaining = total_income - total_expense
    status, rate = get_budget_status(total_income, total_expense)
    max_category, advice = get_consumption_type()

    elements.append(Paragraph("대학생 월별 예산 관리 소비상태 보고서", title_style))
    elements.append(Spacer(1, 16))

    elements.append(Paragraph(f"작성일: {date.today()}", normal_style))
    elements.append(Spacer(1, 12))

    summary_data = [
        ["항목", "금액"],
        ["총수입", f"{total_income:,}원"],
        ["총지출", f"{total_expense:,}원"],
        ["남은 금액", f"{remaining:,}원"],
        ["목표 저축 금액", f"{saving_goal:,}원"],
        ["예산 사용률", f"{rate:.1f}%"],
        ["예산 상태", status],
        ["가장 큰 지출 항목", max_category]
    ]

    table = Table(summary_data, colWidths=[150, 250])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 18))

    elements.append(Paragraph("소비 진단", title_style))
    elements.append(Paragraph(advice, normal_style))
    elements.append(Spacer(1, 18))

    if len(st.session_state.expense_records) > 0:
        elements.append(Paragraph("지출 기록", title_style))

        expense_df = pd.DataFrame(st.session_state.expense_records)
        record_data = [["날짜", "항목", "내용", "금액"]]

        for _, row in expense_df.iterrows():
            record_data.append([
                str(row["날짜"]),
                str(row["항목"]),
                str(row["내용"]),
                f"{int(row['금액']):,}원"
            ])

        record_table = Table(record_data, colWidths=[90, 90, 180, 90])
        record_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(record_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# -----------------------------
# 사이드바
# -----------------------------
menu = st.sidebar.radio(
    "메뉴 선택",
    ["홈", "수입 입력", "지출 입력", "예산 분석", "소비 진단", "장학금 검색", "할인 정보", "PDF 보고서"]
)


# -----------------------------
# 홈
# -----------------------------
if menu == "홈":
    st.header("웹앱 소개")

    st.write("""
    이 웹앱은 대학생의 월별 수입과 지출을 관리하고,
    소비 습관을 분석하여 더 계획적인 소비를 돕는 예산 관리 웹앱입니다.
    """)

    st.subheader("주요 기능")
    st.write("""
    - 월별 수입 입력
    - 세부 지출 기록
    - 예산 사용률 분석
    - 소비 유형 진단
    - 장학금 검색
    - 할인 정보 검색
    - PDF 소비상태 보고서 다운로드
    """)


# -----------------------------
# 수입 입력
# -----------------------------
elif menu == "수입 입력":
    st.header("월별 수입 입력")

    income = st.session_state.income_data

    st.subheader("⭐ 목표 저축 금액")
    saving_goal = st.number_input(
        "이번 달 목표 저축 금액",
        min_value=0,
        step=1000,
        value=st.session_state.saving_goal
    )

    st.info("목표 저축 금액은 예산 분석에서 남은 금액과 비교됩니다.")

    st.divider()

    st.subheader("수입 항목 입력")

    allowance = st.number_input("용돈", min_value=0, step=1000, value=income.get("용돈", 0))
    part_time = st.number_input("아르바이트비", min_value=0, step=1000, value=income.get("아르바이트비", 0))
    scholarship = st.number_input("장학금", min_value=0, step=1000, value=income.get("장학금", 0))

    investment = st.number_input(
        "주식/투자 수익",
        step=1000,
        value=income.get("주식/투자 수익", 0)
    )

    etc_income = st.number_input("기타 수입", min_value=0, step=1000, value=income.get("기타 수입", 0))

    if st.button("수입 저장"):
        st.session_state.income_data = {
            "용돈": allowance,
            "아르바이트비": part_time,
            "장학금": scholarship,
            "주식/투자 수익": investment,
            "기타 수입": etc_income
        }
        st.session_state.saving_goal = saving_goal
        st.success("수입 정보가 저장되었습니다.")

    total_income = sum(st.session_state.income_data.values())
    st.metric("현재 저장된 총수입", f"{total_income:,}원")

# -----------------------------
# 지출 입력
# -----------------------------
elif menu == "지출 입력":
    st.header("월별 지출 입력")

    st.write("지출을 하나씩 기록하면 항목별 총지출이 자동으로 계산됩니다.")

    col1, col2, col3 = st.columns(3)

    with col1:
        expense_date = st.date_input("날짜")

    with col2:
        expense_category = st.selectbox(
            "지출 항목",
            ["식비", "카페/간식", "교통비", "쇼핑", "여가/문화", "고정지출", "기타 지출"]
        )

    with col3:
        expense_amount = st.number_input("금액", min_value=0, step=1000)

    expense_memo = st.text_input("내용", placeholder="예: 학식, 커피, 지하철, 교재 구입")

    if st.button("지출 추가"):
        if expense_amount <= 0:
            st.warning("금액을 입력해주세요.")
        else:
            new_record = {
                "날짜": str(expense_date),
                "항목": expense_category,
                "내용": expense_memo,
                "금액": int(expense_amount)
            }

            st.session_state.expense_records.append(new_record)
            update_expense_summary()
            st.success("지출이 추가되었습니다.")

    st.divider()

    st.subheader("지출 기록")

    if len(st.session_state.expense_records) == 0:
        st.info("아직 입력된 지출 기록이 없습니다.")
    else:
        expense_record_df = pd.DataFrame(st.session_state.expense_records)
        st.dataframe(expense_record_df, use_container_width=True)

        total_expense = expense_record_df["금액"].sum()
        st.metric("총지출", f"{total_expense:,}원")

        if st.button("전체 지출 기록 삭제"):
            st.session_state.expense_records = []
            st.session_state.expense_data = {}
            st.warning("전체 지출 기록이 삭제되었습니다.")


# -----------------------------
# 예산 분석
# -----------------------------
elif menu == "예산 분석":
    st.header("예산 분석")

    update_expense_summary()

    total_income = sum(st.session_state.income_data.values())
    total_expense = sum(st.session_state.expense_data.values())
    saving_goal = st.session_state.saving_goal
    remaining = total_income - total_expense

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("총수입", f"{total_income:,}원")
    col2.metric("총지출", f"{total_expense:,}원")
    col3.metric("남은 금액", f"{remaining:,}원")
    col4.metric("목표 저축 금액", f"{saving_goal:,}원")

    st.divider()

    status, expense_rate = get_budget_status(total_income, total_expense)

    if total_income == 0:
        st.warning("먼저 수입 정보를 입력해주세요.")
    else:
        st.subheader("예산 사용률")
        st.progress(min(expense_rate / 100, 1.0))
        st.write(f"현재 예산의 **{expense_rate:.1f}%**를 사용했습니다.")

        if status == "안정":
            st.success("예산 상태: 안정")
            st.write("아직 예산에 여유가 있습니다.")
        elif status == "주의":
            st.info("예산 상태: 주의")
            st.write("지출이 조금씩 커지고 있습니다.")
        elif status == "위험":
            st.warning("예산 상태: 위험")
            st.write("예산을 거의 다 사용했습니다.")
        elif status == "초과":
            st.error("예산 상태: 초과")
            st.write("이미 예산을 초과했습니다.")

        if remaining < 0:
            st.error(f"예산을 {-remaining:,}원 초과했습니다.")
        elif remaining >= saving_goal:
            st.success("목표 저축 금액을 달성할 수 있습니다.")
        else:
            shortage = saving_goal - remaining
            st.warning(f"목표 저축 금액보다 {shortage:,}원 부족합니다.")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("수입 항목별 비율")
        income_df = pd.DataFrame({
            "항목": list(st.session_state.income_data.keys()),
            "금액": list(st.session_state.income_data.values())
        })
        income_df = income_df[income_df["금액"] > 0]

        if len(income_df) > 0:
            fig_income = px.pie(income_df, names="항목", values="금액")
            st.plotly_chart(fig_income, use_container_width=True)
        else:
            st.info("수입 데이터가 없습니다.")

    with col_b:
        st.subheader("지출 항목별 비율")
        expense_df = pd.DataFrame({
            "항목": list(st.session_state.expense_data.keys()),
            "금액": list(st.session_state.expense_data.values())
        })
        expense_df = expense_df[expense_df["금액"] > 0]

        if len(expense_df) > 0:
            fig_expense = px.pie(expense_df, names="항목", values="금액")
            st.plotly_chart(fig_expense, use_container_width=True)
        else:
            st.info("지출 데이터가 없습니다.")

    st.subheader("항목별 지출 막대그래프")

    if len(st.session_state.expense_data) > 0:
        expense_bar_df = pd.DataFrame({
            "항목": list(st.session_state.expense_data.keys()),
            "금액": list(st.session_state.expense_data.values())
        })

        fig_bar = px.bar(expense_bar_df, x="항목", y="금액", text="금액")
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("지출 데이터가 없습니다.")


# -----------------------------
# 소비 진단
# -----------------------------
elif menu == "소비 진단":
    st.header("소비 유형 진단")

    update_expense_summary()

    if len(st.session_state.expense_data) == 0 or sum(st.session_state.expense_data.values()) == 0:
        st.warning("먼저 지출 정보를 입력해주세요.")
    else:
        expense_data = st.session_state.expense_data
        total_expense = sum(expense_data.values())
        max_category = max(expense_data, key=expense_data.get)
        max_amount = expense_data[max_category]
        max_rate = max_amount / total_expense * 100

        st.metric("가장 큰 지출 항목", max_category)
        st.write(f"{max_category} 항목이 전체 지출의 **{max_rate:.1f}%**를 차지합니다.")

        st.divider()

        _, advice = get_consumption_type()
        st.subheader("소비 유형 분석")
        st.write(advice)

        st.divider()

        recommended_cut = int(max_amount * 0.1)
        st.subheader("절약 목표 추천")
        st.write(f"다음 달에는 **{max_category}** 항목에서 약 **{recommended_cut:,}원** 정도 줄이는 것을 목표로 해보세요.")


# -----------------------------
# 장학금 검색
# -----------------------------
elif menu == "장학금 검색":
    st.header("장학금 검색")

    col1, col2 = st.columns(2)

    with col1:
        school = st.text_input("학교명")
        major = st.text_input("학과/전공")

    with col2:
        scholarship_type = st.selectbox(
            "관심 장학금 유형",
            ["전체", "교내장학금", "교외장학금", "국가장학금", "생활비 장학금", "성적 장학금"]
        )
        extra_keyword = st.text_input("추가 검색어", value="")

    quick_search = st.radio(
        "빠른 검색",
        ["직접 입력", "서울대학교 장학금", "국가장학금", "생활비 장학금"],
        horizontal=True
    )

    if quick_search == "서울대학교 장학금":
        school = "서울대학교"
        major = ""
        scholarship_type = "전체"
    elif quick_search == "국가장학금":
        school = ""
        major = ""
        scholarship_type = "국가장학금"
    elif quick_search == "생활비 장학금":
        school = ""
        major = ""
        scholarship_type = "생활비 장학금"

    if st.button("장학금 검색하기"):
        keyword_parts = []

        if school:
            keyword_parts.append(school)

        if major:
            keyword_parts.append(major)

        if scholarship_type != "전체":
            keyword_parts.append(scholarship_type)

        keyword_parts.append("장학금")

        if extra_keyword:
            keyword_parts.append(extra_keyword)

        keyword = " ".join(keyword_parts)

        st.write(f"검색어: **{keyword}**")

        scholarship_df = search_scholarships(keyword)

        st.subheader("검색 결과")
        st.dataframe(scholarship_df, use_container_width=True)

        st.info("주의: 신청 기간과 자격 조건은 반드시 공식 홈페이지에서 다시 확인해야 합니다.")


# -----------------------------
# 할인 정보
# -----------------------------
elif menu == "할인 정보":
    st.header("맞춤형 할인 정보 검색")

    category = st.selectbox(
        "할인 정보를 찾고 싶은 분야",
        ["식비", "카페/간식", "쇼핑", "여가/문화", "교통비", "직접 입력"]
    )

    if category == "직접 입력":
        custom_keyword = st.text_input("검색어를 입력하세요", placeholder="예: 아이패드 필름 할인")
        store_keyword = ""
    else:
        custom_keyword = ""
        store_keyword = st.text_input("브랜드/장소 추가 입력", placeholder="예: 올리브영, 배민, CGV, 무신사")

    if st.button("할인 정보 검색하기"):
        if category == "직접 입력":
            keyword = custom_keyword
        else:
            keyword_map = {
                "식비": "편의점 음식 배달 할인 쿠폰",
                "카페/간식": "카페 디저트 할인 쿠폰",
                "쇼핑": "쇼핑몰 세일 할인 쿠폰",
                "여가/문화": "영화 전시 공연 할인",
                "교통비": "대중교통 교통비 할인"
            }

            keyword = keyword_map[category]

            if store_keyword:
                keyword = f"{store_keyword} {keyword}"

        if not keyword:
            st.warning("검색어를 입력해주세요.")
        else:
            st.write(f"검색어: **{keyword}**")

            discount_df = search_discounts(keyword)

            st.subheader("할인 정보 검색 결과")
            st.dataframe(discount_df, use_container_width=True)

            st.info("주의: 할인 정보는 검색 결과 기반이므로 실제 적용 여부와 기간은 공식 페이지에서 확인해야 합니다.")


# -----------------------------
# PDF 보고서
# -----------------------------
elif menu == "PDF 보고서":
    st.header("소비상태 PDF 보고서")

    update_expense_summary()

    total_income = sum(st.session_state.income_data.values())
    total_expense = sum(st.session_state.expense_data.values())
    remaining = total_income - total_expense
    status, rate = get_budget_status(total_income, total_expense)
    max_category, advice = get_consumption_type()

    st.subheader("보고서 미리보기")

    st.write(f"총수입: **{total_income:,}원**")
    st.write(f"총지출: **{total_expense:,}원**")
    st.write(f"남은 금액: **{remaining:,}원**")
    st.write(f"예산 사용률: **{rate:.1f}%**")
    st.write(f"예산 상태: **{status}**")
    st.write(f"가장 큰 지출 항목: **{max_category}**")
    st.write(advice)

    pdf_buffer = create_pdf_report()

    st.download_button(
        label="PDF 보고서 다운로드",
        data=pdf_buffer,
        file_name="budget_report.pdf",
        mime="application/pdf"
    )
