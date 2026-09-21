"""Offline grading and reporting checks with vendor-independent fixtures."""
from widesearch_bench.schema import ArmRun, GoldEntity, Task, TaskType
from widesearch_bench.grading import grade
from widesearch_bench.runner import build_report


def test_report_matches_synthetic_observations_and_ignores_arm_names():
    tasks = [Task(id=f'synthetic-{i}', type=TaskType.T1_ENUM, question='q',
                  gold_entities=[GoldEntity(f'Entity {j}') for j in range(8)],
                  as_of='2026-09-18', set_size='M', min_gold_domains=0)
             for i in range(6)]
    def report_for(names):
        grades = []
        for task in tasks:
            for arm, covered in zip(names, [3, 6, 7]):
                for repeat in range(3):
                    found = [g.canonical for g in task.gold_entities[:covered]]
                    run = ArmRun(task.id, arm, repeat, answer_entities=found,
                                 api_calls=2, downstream_tokens=100)
                    grades.append(grade(task, run, ' '.join(found)))
        return build_report(tasks, grades, names)
    names = ['configuration-a', 'configuration-b', 'configuration-c']
    report = report_for(names)
    renamed = report_for(list(reversed(names)))
    for arm, renamed_arm, covered in zip(names, reversed(names), [3, 6, 7]):
        expected = round(2 * covered / (8 + covered), 4)
        assert report['arms'][arm]['f1_mean'] == expected
        assert report['arms'][arm] == renamed['arms'][renamed_arm]
        assert report['arms'][arm]['n_tasks'] == 6
        assert report['arms'][arm]['n_attempts'] == 18
    assert len(report['comparisons']) == 3
