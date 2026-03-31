import re

with open(r'C:\MykeyC\失敗しない本の買い方３（コピペ用）.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all g elements with id
nodes = []
for m in re.finditer(r'<g\s+[^>]*\bid="(\d+)"', content):
    node_id = m.group(1)
    start = m.start()
    # Find closing tag
    depth = 0
    pos = start
    while pos < len(content):
        if content[pos:pos+2] == '<g':
            depth += 1
        elif content[pos:pos+4] == '</g>':
            depth -= 1
            if depth == 0:
                block = content[start:pos+4]
                break
        pos += 1
    else:
        continue

    # Extract parentid
    pid_match = re.search(r'ed:parentid="([^"]+)"', block)
    parentid = pid_match.group(1) if pid_match else None

    # Extract fill color from first path/rect
    fill_match = re.search(r'fill="(#[0-9a-fA-F]+)"', block[:600])
    fill = fill_match.group(1) if fill_match else None

    # Extract text from first <text> block
    first_text_match = re.search(r'<text[^>]*>(.*?)</text>', block, re.DOTALL)
    texts = []
    if first_text_match:
        tspans = re.findall(r'<tspan[^>]*>([^<]+)</tspan>', first_text_match.group(1))
        texts = [t.strip() for t in tspans if t.strip()]

    # Extract topictype
    tt_match = re.search(r'ed:topictype="([^"]+)"', block)
    topictype = tt_match.group(1) if tt_match else None

    nodes.append({
        'id': node_id,
        'parentid': parentid,
        'fill': fill,
        'texts': texts,
        'topictype': topictype
    })

for b in nodes:
    text_str = ' | '.join(b['texts']) if b['texts'] else '(no text)'
    print(f"id={b['id']} parent={b['parentid']} fill={b['fill']} type={b['topictype']} text={text_str}")
