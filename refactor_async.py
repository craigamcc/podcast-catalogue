import re

filepath = '/Users/craigmccosker/Developer/podcast-catalogue/podcast_catalogue/server.py'
with open(filepath, 'r') as f:
    text = f.read()

# 1. Replace "@mcp.tool()\ndef " with "@mcp.tool()\nasync def " if the function uses asyncio.run
def fix_def(match):
    header = match.group(0)
    start_idx = match.end()
    end_idx = text.find('@mcp.tool()', start_idx)
    if end_idx == -1: end_idx = len(text)
    
    body = text[start_idx:end_idx]
    if 'asyncio.run(' in body: 
        return match.group(1) + '\nasync def ' + match.group(2)
    return header

text = re.sub(r'(@mcp\.tool\(\)\n(?:@[^\n]+\n)*)def ([^\(]+\()', fix_def, text)

# 2. Replace 'asyncio.run(' with 'await ' for these inner tools
# For direct calls: asyncio.run(_process()) -> await _process()
text = re.sub(r'asyncio\.run\((.*?)\)', r'await \1', text)

with open(filepath, 'w') as f:
    f.write(text)

print("Refactored asyncio.run to await.")
