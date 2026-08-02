from __future__ import annotations

import html
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "docs"
OUTPUT_FILE = OUTPUT_DIR / "bubibi_modusign_template.docx"


def text_run(text: str, bold: bool = False, size: int | None = None) -> str:
    props = ""

    if bold or size:
        prop_parts = []

        if bold:
            prop_parts.append("<w:b/>")

        if size:
            prop_parts.append(f'<w:sz w:val="{size}"/>')

        props = f"<w:rPr>{''.join(prop_parts)}</w:rPr>"

    return f"<w:r>{props}<w:t>{html.escape(text)}</w:t></w:r>"


def paragraph(text: str = "", *, bold: bool = False, size: int | None = None) -> str:
    return f"<w:p>{text_run(text, bold=bold, size=size)}</w:p>"


def spacer() -> str:
    return '<w:p><w:r><w:br/></w:r></w:p>'


def table(rows: list[tuple[str, str]]) -> str:
    row_xml = []

    for label, value in rows:
        row_xml.append(
            "<w:tr>"
            "<w:tc><w:tcPr><w:tcW w:w=\"2600\" w:type=\"dxa\"/></w:tcPr>"
            f"{paragraph(label, bold=True)}</w:tc>"
            "<w:tc><w:tcPr><w:tcW w:w=\"6600\" w:type=\"dxa\"/></w:tcPr>"
            f"{paragraph(value)}</w:tc>"
            "</w:tr>"
        )

    return (
        "<w:tbl>"
        "<w:tblPr>"
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"D9E0E8\"/>"
        "<w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"D9E0E8\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"D9E0E8\"/>"
        "<w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"D9E0E8\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"D9E0E8\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"D9E0E8\"/>"
        "</w:tblBorders>"
        "</w:tblPr>"
        f"{''.join(row_xml)}"
        "</w:tbl>"
    )


def build_document_xml() -> str:
    body = [
        paragraph("부비비 예약 조건 확인서", bold=True, size=40),
        paragraph("온라인 예약 약관/조건 AI 요약 확인 기록", size=22),
        spacer(),
        paragraph(
            "이 문서는 여행객이 부비비를 통해 온라인 예약 조건의 주요 주의사항을 확인했다는 기록입니다."
        ),
        paragraph(
            "AI 요약은 이해 보조 목적이며, 원문 전체를 대체하지 않습니다."
        ),
        spacer(),
        paragraph("1. 예약 출처", bold=True, size=28),
        table(
            [
                ("예약 출처", "[예약출처]"),
                ("예약 URL", "[예약URL]"),
                ("확인 시각", "[확인시각]"),
            ]
        ),
        spacer(),
        paragraph("2. AI 분석 요약", bold=True, size=28),
        table([("분석 요약", "[분석요약]")]),
        spacer(),
        paragraph("3. 여행객이 확인한 주의사항", bold=True, size=28),
        table([("확인 카드", "[확인카드]")]),
        spacer(),
        paragraph("4. AI 생성 내용 고지", bold=True, size=28),
        table([("고지", "[AI고지]")]),
        spacer(),
        paragraph("5. 여행객 확인", bold=True, size=28),
        paragraph(
            "본인은 위 예약 조건 요약 카드와 원문 출처를 확인했으며, 필요한 경우 예약처 또는 공급업체에 추가 확인을 진행할 수 있음을 이해했습니다."
        ),
        spacer(),
        table(
            [
                ("여행객 이름", "[여행객 이름]"),
                ("여행객 서명", "[여행객 서명]"),
                ("서명일", "[서명일]"),
            ]
        ),
        spacer(),
        paragraph("모두싸인 템플릿 설정 메모", bold=True, size=24),
        paragraph("참여자 역할명: 여행객"),
        paragraph("요청자 입력 데이터 라벨: 분석요약, 예약URL, 예약출처, 확인카드, 확인시각, AI고지"),
        paragraph("서명자 필드 데이터 라벨 예시: 여행객 서명, 서명일"),
    ]

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {''.join(body)}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


def write_docx() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    document_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""

    with zipfile.ZipFile(OUTPUT_FILE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/_rels/document.xml.rels", document_rels)
        archive.writestr("word/document.xml", build_document_xml())

    print(OUTPUT_FILE)


if __name__ == "__main__":
    write_docx()
