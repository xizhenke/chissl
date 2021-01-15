import ipywidgets as widgets
from traitlets import Dict

from .react_jupyter_widget import ReactJupyterWidget

import numpy as np
import pandas as pd

from umap import UMAP
from sklearn.cluster import AgglomerativeClustering
from scipy.spatial.distance import cdist

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba_array, rgb2hex

def get_cost(X, children):

    n = len(X) + len(children)

    X_tot = np.zeros((n, X.shape[1]))
    X_tot[:len(X)] = X

    N = np.zeros(n)
    N[:len(X)] = 1

    C = np.zeros(n)

    for i,(u,v) in enumerate(children):
        p = i + len(X)

        X_tot[p] = X_tot[u] + X_tot[v]
        N[p] = N[u] + N[v]

        xu = X_tot[u]/N[u]
        xv = X_tot[v]/N[v]
        xp = X_tot[p]/N[p]

        C[u], C[v] = cdist([xp], [xu, xv]).flat
        
    return C

def cluster(X, **kwargs):
    children = AgglomerativeClustering(**kwargs)\
        .fit(X)\
        .children_

    n = len(X)
    m = len(children)

    left, right = children.T
    parents = np.arange(n + m)
    parents[left] = parents[right] = np.arange(m) + n

    return parents, get_cost(X, children)

@widgets.register
class ChisslWidget(ReactJupyterWidget):
    predictions = Dict().tag(sync=True)

    def __init__(self, X, y=None, features=None, semi_supervised=False, **kwargs):

        if type(X) is not pd.DataFrame:
            X = pd.DataFrame(X)

        self.X = X
        self.umap = UMAP(random_state=1234567890)

        umap_kwargs = dict(X=X)

        if 'labels' in kwargs and 'colors' not in kwargs:
            kwargs['colors'] = {
                v: rgb2hex(plt.cm.tab10(i%10))
                for i, v in enumerate(kwargs['labels'].values())
            }

        if semi_supervised and 'labels' in kwargs:
            umap_kwargs['y'] = self.get_y_from_labels(kwargs['labels'])

        self.xy = xy = self.umap.fit_transform(**umap_kwargs)

        parents, costs = cluster(self.xy, linkage='ward')

        props = {
           'parents': parents.tolist(),
           'costs': costs.tolist(),
           'instances': X.index.astype(str).tolist(),
           'X': xy.tolist(),
        }

        if features is not None:
            props['hist'] = features.to_dict(orient='list')

        super().__init__(**props, **kwargs)

    def scatter(self, ax=None, **kwargs):
        ax = ax or plt.gca()

        colors = self.state['colors']
        y_pred = self.predictions['classes'][:len(self.xy)]
        c = to_rgba_array(list(map(colors.get, y_pred)))

        ax.scatter(*self.xy.T, c=c, **kwargs)

        ax.legend(
            [plt.Rectangle((0, 0), 0, 0, color=v) for v in colors.values()],
            colors
        )

    def get_y_from_labels(self, labels):
        _, inverse = np.unique(list(labels.values()), return_inverse=True)
        
        return pd.Series(data=inverse, index=labels)\
            .reindex(self.X.index)\
            .fillna(-1)\
            .astype(int)
