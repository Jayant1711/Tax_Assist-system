from ai_models import UniversalParser, SemanticAttention

p = UniversalParser()
attn = SemanticAttention()

# Debug P15
print("=== P15 Debug ===")
for m in p.digit_pat.finditer('45k pm'):
    rest = '45k pm'[m.end():m.end()+10]
    print(f"match={repr(m.group(0))} unit={m.group(2)} rest={repr(rest)}")

r = p.parse('45k pm')
print("parse result:", [(x['val'], x['start'], x['end']) for x in r])

# Debug C05b
print("\n=== C05b Debug ===")
sent = 'I earn 50L from salary, 10L from rental, and I paid 1.5L in PPF'
results = p.parse(sent)
for r in results:
    cat = attn.resolve_category(sent, r['start'], r['end'], 'Salaried')
    ctx = sent[max(0, r['start']-15): r['end']+15]
    print(f"  val={r['val']:,.0f} pos=[{r['start']}:{r['end']}] cat={cat} ctx={repr(ctx)}")
