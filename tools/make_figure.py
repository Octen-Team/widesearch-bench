"""Plot generated reference metrics with equal emphasis for every configuration.

Usage: python tools/make_figure.py [--out figures/widesearch_results.png]
Rebuild results/summary.json with tools/release_report.py first.
"""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main(out):
    data=json.loads((ROOT/'results/summary.json').read_text())
    arms=sorted(data['arms']);names=['Exa instant','Octen broad_search','Parallel turbo','Tavily ultrafast']
    fig,axes=plt.subplots(2,2,figsize=(13,8.5),layout='constrained')
    x=np.arange(len(arms));color='#46596c'
    for ax,key,title in [(axes[0,0],'arms','Entity-F1 · pooled gold'),(axes[0,1],'strict_arms','Entity-F1 · strict gold')]:
        means=np.array([data[key][a]['f1'] for a in arms]);ci=np.array([data[key][a]['ci'] for a in arms])
        ax.bar(x,means,color=color,width=.55,yerr=[means-ci[:,0],ci[:,1]-means],capsize=4)
        for i,v in enumerate(means):ax.text(i,ci[i,1]+.015,f'{v:.3f}',ha='center')
        ax.set_ylim(0,max(ci[:,1])+.10);ax.set_ylabel('Mean F1; marginal 95% bootstrap interval')
        ax.set_title(title)
    for ax,key,title,label in [(axes[1,0],'e2e_time_s','End-to-end time · successful attempts','seconds'),(axes[1,1],'downstream_tokens','Recorded downstream usage · successful attempts','tokens')]:
        values=[data['arms'][a][key] for a in arms]
        ax.bar(x,values,color=color,width=.55)
        for i,v in enumerate(values):ax.text(i,v*1.025,f'{v:,.1f}',ha='center')
        ax.set_ylim(0,max(values)*1.2);ax.set_ylabel(label);ax.set_title(title)
    for ax in axes.flat:
        ax.set_xticks(x,names,rotation=10);ax.spines[['top','right']].set_visible(False)
        ax.set_axisbelow(True);ax.grid(axis='y',alpha=.2)
    fig.suptitle(f"WideSearch-Bench · {data['tasks']} questions · {data['errors']} recorded failures\n"
                 'Recorded configurations differ in backends, excerpts and retry policies',fontsize=14)
    fig.supxlabel('Quality includes failures as zero. Cost excludes failures; n = '+
                  ', '.join(str(data['arms'][a]['successes']) for a in arms)+
                  '. Historical HTTP attempts and full billing usage are unavailable.',fontsize=9)
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    matplotlib.rcParams['svg.hashsalt']='widesearch-reference'
    fig.savefig(out,dpi=170,metadata={'Software':'WideSearch-Bench'})
    fig.savefig(out.with_suffix('.svg'),metadata={'Date':None,'Creator':'WideSearch-Bench'})
    svg = out.with_suffix('.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default=str(ROOT/'figures/widesearch_results.png'))
    main(p.parse_args().out)
