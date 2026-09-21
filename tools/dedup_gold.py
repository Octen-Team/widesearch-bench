"""Apply reviewed identity decisions, never fuzzy scoring matches.

A scoring collision is not proof that two names refer to one entity. By default
only identical Unicode/case/whitespace forms are merged. --decisions supplies
explicit per-question decisions from data/identity_decisions.json. Existing
aliases remain scoped to the input variant. --check never writes files.
"""
import argparse
import json
import unicodedata


def identity_key(name):
    return ' '.join(unicodedata.normalize('NFKC', name).casefold().split())


def group(golds, approved_groups=()):
    lookup = {identity_key(name): i for i, names in enumerate(approved_groups) for name in names}
    groups, indices = [], {}
    for i, gold in enumerate(golds):
        name = identity_key(gold['canonical'])
        key = ('approved', lookup[name]) if name in lookup else ('exact', name)
        if key not in indices:
            indices[key] = len(groups)
            groups.append([])
        groups[indices[key]].append(i)
    return groups


def merge(golds, indices, canonical=None):
    members = [golds[i] for i in indices]
    canonical = canonical or members[0]['canonical']
    aliases = []
    for member in members:
        for form in [member['canonical'], *member.get('aliases', [])]:
            if form != canonical and form not in aliases:
                aliases.append(form)
    return {'canonical': canonical, 'aliases': aliases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tasks')
    parser.add_argument('--decisions')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    decisions = json.load(open(args.decisions))['decisions'] if args.decisions else []
    rows = [json.loads(line) for line in open(args.tasks) if line.strip()]
    changed = 0
    for row in rows:
        rules = [d for d in decisions if d['task_id'] == row['id']]
        excluded = {n for d in rules if d['action'] == 'exclude' for n in d['members']}
        golds = [g for g in row['gold_entities'] if g['canonical'] not in excluded]
        merged = [d for d in rules if d['action'] == 'merge']
        groups = group(golds, [[d['canonical'], *d['members']] for d in merged])
        output = []
        for indices in groups:
            name = golds[indices[0]]['canonical']
            rule = next((d for d in merged if name in [d['canonical'], *d['members']]), None)
            entity = merge(golds, indices, rule['canonical'] if rule else None)
            for change in rules:
                if change.get('canonical') != entity['canonical']:
                    continue
                entity['aliases'] = list(dict.fromkeys([
                    *entity['aliases'], *change.get('aliases', [])]))
                entity['aliases'] = [a for a in entity['aliases']
                    if a != entity['canonical'] and a not in change.get('remove_aliases', [])]
            output.append(entity)
        changed += output != row['gold_entities']
        row['gold_entities'] = output
    print(f'{changed} tasks require identity corrections')
    if args.check:
        raise SystemExit(bool(changed))
    with open(args.tasks, 'w', encoding='utf-8') as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
