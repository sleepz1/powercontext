"""Generate the one-page contest report from recorded real measurements.
Optional tooling: Python + reportlab + pypdf; not required to run the app.
"""
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from pypdf import PdfReader

root = Path(__file__).resolve().parents[1]
report = json.loads((root / 'results/benchmark.json').read_text(encoding='utf-8'))
verification = json.loads((root / 'results/verification.json').read_text(encoding='utf-8'))
font_path = Path('C:/Windows/Fonts/simhei.ttf')
if not font_path.exists():
    raise SystemExit('Set font_path in this script to an installed CJK TrueType font.')
pdfmetrics.registerFont(TTFont('CJK', str(font_path)))
output = root / 'output/pdf/technical-report.pdf'
output.parent.mkdir(parents=True, exist_ok=True)
green = colors.HexColor('#194b3f')
styles = {
    'title': ParagraphStyle('title', fontName='CJK', fontSize=21, leading=27, textColor=green, spaceAfter=6),
    'sub': ParagraphStyle('sub', fontName='CJK', fontSize=8, leading=12, textColor=colors.HexColor('#63776b'), spaceAfter=13),
    'head': ParagraphStyle('head', fontName='CJK', fontSize=10, leading=15, textColor=green, spaceBefore=9, spaceAfter=3),
    'body': ParagraphStyle('body', fontName='CJK', fontSize=8.5, leading=13, wordWrap='CJK', textColor=colors.HexColor('#2f4038'), spaceAfter=3),
    'cell': ParagraphStyle('cell', fontName='CJK', fontSize=8, leading=11, wordWrap='CJK'),
}
story = []
def para(text, kind='body'):
    story.append(Paragraph(escape(text), styles[kind]))

para('知页 LOCALFOLIO', 'title')
para('04 端侧 AI 推理性能优化与 seekdb 混合检索  |  一页技术说明  |  2026-10-28', 'sub')
para('01  完整链路与正确性', 'head')
para('TXT/MD → 500 字符分块（重叠 60）→ 浏览器 Worker 向量化 → seekdb-js upsert + refresh_index → 数据库内全文/HNSW/RRF → 带出处的结果。文档与查询都在浏览器计算；服务端关闭自动 embedding，不在客户端拼接两路结果。哈希 ID 保证重复导入幂等，集合指纹隔离会话和精度。')
para('02  固定模型与运行环境', 'head')
para('Xenova/multilingual-e5-small，384 维、mean pooling、归一化，使用 query:/passage: 前缀。revision: ' + report['model']['revision'])
manifest = report['manifest']
para(f"ONNX 权重：FP32 {manifest['fp32Bytes']:,} 字节 → INT8 {manifest['int8Bytes']:,} 字节；压缩 {manifest['compressionRatio']:.3f} 倍，减少 {(1-manifest['int8Bytes']/manifest['fp32Bytes'])*100:.2f}%。共享 tokenizer/config 另计；逐文件 SHA-256 在原始 JSON。")
para('Ryzen 9 7945HX / 32 线程，15.69 GiB RAM，RTX 4060 Laptop；Windows / Edge 156 无头独立会话。WSL2 Ubuntu 24.04 + seekdb 1.4.0.0；Node 22.20.0、seekdb-js 1.4.0、Transformers.js 3.8.1；WASM 单线程。')
para('03  真实测量：质量与性能', 'head')
para('生产构建，12 份人工公开示例、6 条标签查询。每配置 3 次语料向量化、3 轮查询，中位数计时；每配置使用独立数据库集合。')
rows = [['配置', '实际后端', '分块/秒', '端到端 ms', 'Recall@5', 'nDCG@5']]
labels = ['FP32 / batch 1', 'INT8 / batch 1', 'INT8 / batch 8', 'INT8 / 自动 / batch 8']
for label, run in zip(labels, report['runs']):
    device = run['actualBackend']['device'].upper()
    if run['config']['backend'] == 'auto' and device == 'WASM': device += ' 回退'
    rows.append([label, device, f"{run['documentsPerSecond']:.2f}", f"{run['medianEndToEndMs']:.2f}", f"{run['recallAt5']:.4f}", f"{run['ndcgAt5']:.4f}"])
table = Table([[Paragraph(escape(cell), styles['cell']) for cell in row] for row in rows],
              colWidths=[155, 77, 63, 74, 76, 76], hAlign='LEFT')
table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e4ede4')),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f6f8f3'), colors.white]),
    ('LINEBELOW', (0, 0), (-1, 0), .7, green),
    ('LINEBELOW', (0, -1), (-1, -1), .4, colors.HexColor('#cdd8cc')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
]))
# Fit the actual A4 content width, retaining relative column widths.
table._argW = [w * (A4[0]-68) / sum(table._argW) for w in table._argW]
table._colWidths = table._argW
story.extend([table, Spacer(1, 7)])
baseline, optimized = report['runs'][:2]
para(f"同 batch 1：INT8 吞吐提高 {(optimized['documentsPerSecond']/baseline['documentsPerSecond']-1)*100:.1f}%，查询中位数下降 {(1-optimized['medianEndToEndMs']/baseline['medianEndToEndMs'])*100:.1f}%；该样例集质量未下降。batch 8 没有稳定收益，交互默认 batch 1。")
para('04  后端降级、计时口径与复现', 'head')
para('优先尝试 WebGPU；初始化/执行失败或 3 个公开句子的 GPU/WASM 最小余弦低于 0.99 时回退。本机初始未检查的 GPU 实验 nDCG 降至 0.5509，最终检测并回退 WASM，不宣称 GPU 加速。自动配置吞吐还受预热及顺序影响。数值检查不代替标签评估。')
load = verification['firstInitializationInFreshBrowserContext']['info']['loadMs']
para(f"新浏览器上下文 INT8/WASM 初始化 {load/1000:.3f} 秒，热查询另计；OS 文件缓存可能已热。表中端到端含 Worker/API 往返，不含绘制；写入、刷新和交互绘制近似计时保留在 JSON。小样例结果不能代表大规模质量。")
para('通过：基础测试 4/4、生产构建、真实数据库检查、Edge 完整流程与 390px 布局检查；测试会话无外网 HTTP 请求。复现：npm test；npm run build；npm run test:db；npm run test:browser -- --benchmark。')
para('证据：results/benchmark.json、results/verification.json、results/initial-webgpu-unchecked.json；模型与包版本见锁文件和 manifest，详细启动说明见 README.md。', 'sub')

def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor('#cedacc'))
    canvas.line(34, 29, A4[0]-34, 29)
    canvas.setFont('CJK', 7)
    canvas.setFillColor(colors.HexColor('#718676'))
    canvas.drawString(34, 18, 'LOCALFOLIO  /  本机实测，尚未官方提测或获得分数')
    canvas.drawRightString(A4[0]-34, 18, f'{doc.page} / 1')

doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=34, rightMargin=34, topMargin=29, bottomMargin=39,
                        title='知页 LOCALFOLIO - 04 技术说明', author='LOCALFOLIO')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
reader = PdfReader(output)
assert len(reader.pages) == 1, f'Report must be one page, got {len(reader.pages)}'
assert 'LOCALFOLIO' in reader.pages[0].extract_text()
print(f'Created one-page report: {output}')
