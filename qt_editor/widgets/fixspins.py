import re
import os

with open('texworks_panel.py', 'r', encoding='utf-8') as f:
    text = f.read()

def replacer1(m):
    pre = m.group(1)
    args = m.group(2)
    # The string looks like self._item_changed, "blocks", b_idx, f"shader_config[{i}]", -1, -1
    return f"{pre}editingFinished.connect(lambda p={pre[:-1]}: " + args.replace('partial(', '').replace('))', f")")

# Wait, the simple replace is better:
# val = p.value() internally
def full_rewrite1(m):
    var = m.group(1)[:-1]
    args = m.group(2)
    # the function is self._item_changed
    args = args.replace("self._item_changed, ", "")
    # append val
    if not args.endswith(", p.value()"):
        args = args + ", p.value()"
    return f"{var}.editingFinished.connect(lambda p={var}: self._item_changed({args}))"

text = re.sub(r'([_a-zA-Z0-9]+\.)valueChanged\.connect\(partial\((.*?)\)\)', full_rewrite1, text)

def full_rewrite2(m):
    var = m.group(1)[:-1]
    args = m.group(2)
    args = args.replace("lambda v:", f"lambda p={var}:")
    args = args.replace("str(v)", "str(p.value())")
    return f"{var}.editingFinished.connect({args})"

text = re.sub(r'([_a-zA-Z0-9]+\.)valueChanged\.connect\((lambda v:.*?)\)', full_rewrite2, text)

# For materials valueChanged:
def full_rewrite3(m):
    var = m.group(1)[:-1]
    args = m.group(2)
    return f"{var}.editingFinished.connect({args})"
text = re.sub(r'([_a-zA-Z0-9]+\.)valueChanged\.connect\((self\..*?)\)', full_rewrite3, text)


with open('texworks_panel.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("success")
