# Copyright 2018-2020 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""This module contains functions to construct many-body observables whose expectation
values can be used to simulate molecular properties.
"""
# pylint: disable=too-many-arguments, too-few-public-methods
import numpy as np
from openfermion.ops import FermionOperator
from openfermion.transforms import bravyi_kitaev, jordan_wigner

from . import structure


def _spin2_matrix_elements(sz):
    r"""Builds the table of matrix elements
    :math:`\langle \bm{\alpha}, \bm{\beta} \vert \hat{s}_1 \cdot \hat{s}_2 \vert
    \bm{\gamma}, \bm{\delta} \rangle` of the two-particle spin operator
    :math:`\hat{s}_1 \cdot \hat{s}_2`.

    The matrix elements are evaluated using the expression

    .. math::

        \langle ~ (\alpha, s_{z_\alpha});~ (\beta, s_{z_\beta}) ~ \vert \hat{s}_1 &&
        \cdot \hat{s}_2 \vert ~ (\gamma, s_{z_\gamma}); ~ (\delta, s_{z_\gamma}) ~ \rangle =
        \delta_{\alpha,\delta} \delta_{\beta,\gamma} \\
        && \times \left( \frac{1}{2} \delta_{s_{z_\alpha}, s_{z_\delta}+1}
        \delta_{s_{z_\beta}, s_{z_\gamma}-1} + \frac{1}{2} \delta_{s_{z_\alpha}, s_{z_\delta}-1}
        \delta_{s_{z_\beta}, s_{z_\gamma}+1} + s_{z_\alpha} s_{z_\beta}
        \delta_{s_{z_\alpha}, s_{z_\delta}} \delta_{s_{z_\beta}, s_{z_\gamma}} \right),

    where :math:`\alpha` and :math:`s_{z_\alpha}` refer to the quantum numbers of the spatial
    function and the spin projection, respectively, of the single-particle state
    :math:`\vert \bm{\alpha} \rangle \equiv \vert \alpha, s_{z_\alpha} \rangle`.

    Args:
        sz (array[float]): spin-projection of the single-particle states

    Returns:
        array: NumPy array with the table of matrix elements. The first four columns
        contain the indices :math:`\bm{\alpha}`, :math:`\bm{\beta}`, :math:`\bm{\gamma}`,
        :math:`\bm{\delta}` and the fifth column stores the computed matrix element.

    **Example**

    >>> sz = np.array([0.5, -0.5])
    >>> print(_spin2_matrix_elements(sz))
    [[ 0.    0.    0.    0.    0.25]
     [ 0.    1.    1.    0.   -0.25]
     [ 1.    0.    0.    1.   -0.25]
     [ 1.    1.    1.    1.    0.25]
     [ 0.    1.    0.    1.    0.5 ]
     [ 1.    0.    1.    0.    0.5 ]]
    """

    n = np.arange(sz.size)

    alpha = n.reshape(-1, 1, 1, 1)
    beta = n.reshape(1, -1, 1, 1)
    gamma = n.reshape(1, 1, -1, 1)
    delta = n.reshape(1, 1, 1, -1)

    # we only care about indices satisfying the following boolean mask
    mask = np.logical_and(alpha // 2 == delta // 2, beta // 2 == gamma // 2)

    # diagonal elements
    diag_mask = np.logical_and(sz[alpha] == sz[delta], sz[beta] == sz[gamma])
    diag_indices = np.argwhere(np.logical_and(mask, diag_mask))
    diag_values = (sz[alpha] * sz[beta]).flatten()

    diag = np.vstack([diag_indices.T, diag_values]).T

    # off-diagonal elements
    m1 = np.logical_and(sz[alpha] == sz[delta] + 1, sz[beta] == sz[gamma] - 1)
    m2 = np.logical_and(sz[alpha] == sz[delta] - 1, sz[beta] == sz[gamma] + 1)

    off_diag_mask = np.logical_and(mask, np.logical_or(m1, m2))
    off_diag_indices = np.argwhere(off_diag_mask)
    off_diag_values = np.full([len(off_diag_indices)], 0.5)

    off_diag = np.vstack([off_diag_indices.T, off_diag_values]).T

    # combine the off diagonal and diagonal tables into a single table
    return np.vstack([diag, off_diag])


def spin2(electrons, orbitals, mapping="jordan_wigner", wires=None):
    r"""Computes the total spin operator :math:`\hat{S}^2`.

    The total spin operator :math:`\hat{S}^2` is given by

    .. math::

        \hat{S}^2 = \frac{3}{4}N + \sum_{ \bm{\alpha}, \bm{\beta}, \bm{\gamma}, \bm{\delta} }
        \langle \bm{\alpha}, \bm{\beta} \vert \hat{s}_1 \cdot \hat{s}_2
        \vert \bm{\gamma}, \bm{\delta} \rangle ~
        \hat{c}_\bm{\alpha}^\dagger \hat{c}_\bm{\beta}^\dagger
        \hat{c}_\bm{\gamma} \hat{c}_\bm{\delta},
    
    where the two-particle matrix elements are computed as,

    .. math::

        \langle \bm{\alpha}, \bm{\beta} \vert \hat{s}_1 \cdot \hat{s}_2
        \vert \bm{\gamma}, \bm{\delta} \rangle = && \delta_{\alpha,\delta} \delta_{\beta,\gamma} \\
        && \times \left( \frac{1}{2} \delta_{s_{z_\alpha}, s_{z_\delta}+1}
        \delta_{s_{z_\beta}, s_{z_\gamma}-1} + \frac{1}{2} \delta_{s_{z_\alpha}, s_{z_\delta}-1}
        \delta_{s_{z_\beta}, s_{z_\gamma}+1} + s_{z_\alpha} s_{z_\beta}
        \delta_{s_{z_\alpha}, s_{z_\delta}} \delta_{s_{z_\beta}, s_{z_\gamma}} \right).

    In the equations above :math:`N` is the number of electrons, :math:`\alpha` refer to the
    quantum numbers of the spatial wave function and :math:`s_{z_\alpha}` is
    the spin projection of the single-particle state
    :math:`\vert \bm{\alpha} \rangle \equiv \vert \alpha, s_{z_\alpha} \rangle`.
    The operators :math:`\hat{c}^\dagger` and :math:`\hat{c}` are the particle creation
    and annihilation operators, respectively.

    Args:
        electrons (int): Number of electrons. If an active space is defined, this is
            the number of active electrons.
        orbitals (int): Number of *spin* orbitals. If an active space is defined,  this is
            the number of active spin-orbitals.
        mapping (str): Specifies the transformation to map the fermionic operator to the
            Pauli basis. Input values can be ``'jordan_wigner'`` or ``'bravyi_kitaev'``.
        wires (Wires, list, tuple, dict): Custom wire mapping used to convert the qubit operator
            to an observable measurable in a PennyLane ansatz.
            For types Wires/list/tuple, each item in the iterable represents a wire label
            corresponding to the qubit number equal to its index.
            For type dict, only int-keyed dict (for qubit-to-wire conversion) is accepted.
            If None, will use identity map (e.g. 0->0, 1->1, ...).

    Returns:
        pennylane.Hamiltonian: the total spin observable :math:`\hat{S}^2`

    **Example**

    >>> electrons = 2
    >>> orbitals = 4
    >>> S2 = spin2(electrons, orbitals, mapping="jordan_wigner")
    >>> print(S2)
    (0.75) [I0]
    + (0.375) [Z1]
    + (-0.375) [Z0 Z1]
    + (0.125) [Z0 Z2]
    + (0.375) [Z0]
    + (-0.125) [Z0 Z3]
    + (-0.125) [Z1 Z2]
    + (0.125) [Z1 Z3]
    + (0.375) [Z2]
    + (0.375) [Z3]
    + (-0.375) [Z2 Z3]
    + (0.125) [Y0 X1 Y2 X3]
    + (0.125) [Y0 Y1 X2 X3]
    + (0.125) [Y0 Y1 Y2 Y3]
    + (-0.125) [Y0 X1 X2 Y3]
    + (-0.125) [X0 Y1 Y2 X3]
    + (0.125) [X0 X1 X2 X3]
    + (0.125) [X0 X1 Y2 Y3]
    + (0.125) [X0 Y1 X2 Y3]

    >>> S2 = spin2(electrons, orbitals, mapping="jordan_wigner", wires=['w0','w1','w2','w3'])
    >>> print(S2)
    (0.75) [Iw0]
    + (0.375) [Zw1]
    + (-0.375) [Zw0 Zw1]
    + (0.125) [Zw0 Zw2]
    + (0.375) [Zw0]
    + (-0.125) [Zw0 Zw3]
    + (-0.125) [Zw1 Zw2]
    + (0.125) [Zw1 Zw3]
    + (0.375) [Zw2]
    + (0.375) [Zw3]
    + (-0.375) [Zw2 Zw3]
    + (0.125) [Yw0 Xw1 Yw2 Xw3]
    + (0.125) [Yw0 Yw1 Xw2 Xw3]
    + (0.125) [Yw0 Yw1 Yw2 Yw3]
    + (-0.125) [Yw0 Xw1 Xw2 Yw3]
    + (-0.125) [Xw0 Yw1 Yw2 Xw3]
    + (0.125) [Xw0 Xw1 Xw2 Xw3]
    + (0.125) [Xw0 Xw1 Yw2 Yw3]
    + (0.125) [Xw0 Yw1 Xw2 Yw3]
    """

    if electrons <= 0:
        raise ValueError(
            "'electrons' must be greater than 0; got for 'electrons' {}".format(electrons)
        )

    if orbitals <= 0:
        raise ValueError(
            "'orbitals' must be greater than 0; got for 'orbitals' {}".format(orbitals)
        )

    sz = np.where(np.arange(orbitals) % 2 == 0, 0.5, -0.5)

    table = _spin2_matrix_elements(sz)

    return observable(table, init_term=3 / 4 * electrons, mapping=mapping, wires=wires)


def observable(me_table, init_term=0, mapping="jordan_wigner", wires=None):

    r"""Builds the many-body observable whose expectation value can be
    measured in PennyLane.

    This function can be used to build second-quantized operators in the basis
    of single-particle states (e.g., HF states) and to transform them into
    PennyLane observables. In general, single- and two-particle operators can be
    expanded in a defined active space,

    .. math::

        &&\hat A = \sum_{\alpha \leq 2n_\mathrm{docc}} \langle \alpha \vert \hat{\mathcal{A}}
        \vert \alpha \rangle ~ \hat{n}_\alpha +
        \sum_{\alpha, \beta ~ \in ~ \mathrm{active~space}} \langle \alpha \vert \hat{\mathcal{A}}
        \vert \beta \rangle ~ \hat{c}_\alpha^\dagger\hat{c}_\beta \\
        &&\hat B = \frac{1}{2} \left\{ \sum_{\alpha, \beta \leq 2n_\mathrm{docc}}
        \langle \alpha, \beta \vert \hat{\mathcal{B}} \vert \beta, \alpha \rangle
        ~ \hat{n}_\alpha \hat{n}_\beta + \sum_{\alpha, \beta, \gamma, \delta ~
        \in ~ \mathrm{active~space}} \langle \alpha, \beta \vert \hat{\mathcal{B}}
        \vert \gamma, \delta \rangle ~ \hat{c}_{\alpha}^\dagger \hat{c}_{\beta}^\dagger
        \hat{c}_{\gamma} \hat{c}_{\delta} \right\}.

    In the latter equations :math:`n_\mathrm{docc}` denotes the doubly-occupied orbitals,
    if any, not included in the active space and
    :math:`\langle \alpha \vert \hat{\mathcal{A}} \vert \beta \rangle` and
    :math:`\langle \alpha, \beta \vert\hat{\mathcal{B}} \vert \gamma, \delta \rangle`
    are the matrix elements of the one- and two-particle operators
    :math:`\hat{\mathcal{A}}` and :math:`\hat{\mathcal{B}}`, respectively.

    The function utilizes tools of `OpenFermion <https://github.com/quantumlib/OpenFermion>`_
    to build the second-quantized operator and map it to basis of Pauli matrices via the
    Jordan-Wigner or Bravyi-Kitaev transformation. Finally, the qubit operator is
    converted to a a PennyLane observable by the function :func:`~.convert_observable`.

    Args:
        me_table (array[float]): Numpy array with the table of matrix elements.
            For single-particle operators this array will have shape
            ``(me_table.shape[0], 3)`` with each row containing the indices
            :math:`\alpha`, :math:`\beta` and the matrix element :math:`\langle \alpha \vert
            \hat{\mathcal{A}}\vert \beta \rangle`. For two-particle operators this
            array will have shape ``(me_table.shape[0], 5)`` with each row containing
            the indices :math:`\alpha`, :math:`\beta`, :math:`\gamma`, :math:`\delta` and
            the matrix elements :math:`\langle \alpha, \beta \vert \hat{\mathcal{B}}
            \vert \gamma, \delta \rangle`.
        init_term: the contribution of doubly-occupied orbitals, if any, or other quantity
            required to initialize the many-body observable.
        mapping (str): specifies the fermion-to-qubit mapping. Input values can
            be ``'jordan_wigner'`` or ``'bravyi_kitaev'``.
        wires (Wires, list, tuple, dict): Custom wire mapping used to convert the qubit operator
            to an observable measurable in a PennyLane ansatz.
            For types Wires/list/tuple, each item in the iterable represents a wire label
            corresponding to the qubit number equal to its index.
            For type dict, only int-keyed dict (for qubit-to-wire conversion) is accepted.
            If None, will use identity map (e.g. 0->0, 1->1, ...).

    Returns:
        pennylane.Hamiltonian: the fermionic-to-qubit transformed observable

    **Example**

    >>> table = np.array([[0.0, 0.0, 0.4], [1.0, 1.0, -0.5], [1.0, 0.0, 0.0]])
    >>> print(observable(table, init_term=1 / 4, mapping="bravyi_kitaev"))
    (0.2) [I0]
    + (-0.2) [Z0]
    + (0.25) [Z0 Z1]
    >>> print(observable(table, init_term=1 / 4, mapping="bravyi_kitaev", wires=['w0','w1']))
    (0.2) [Iw0]
    + (-0.2) [Zw0]
    + (0.25) [Zw0 Zw1]
    """

    if mapping.strip().lower() not in ("jordan_wigner", "bravyi_kitaev"):
        raise TypeError(
            "The '{}' transformation is not available. \n "
            "Please set 'mapping' to 'jordan_wigner' or 'bravyi_kitaev'.".format(mapping)
        )

    sp_op_shape = (3,)
    tp_op_shape = (5,)
    for i_table in me_table:
        if np.array(i_table).shape not in (sp_op_shape, tp_op_shape):
            raise ValueError(
                "expected entries of 'me_table' to be of shape (3,) or (5,) ; got {}".format(
                    np.array(i_table).shape
                )
            )

    # Initialize the FermionOperator
    mb_obs = FermionOperator() + FermionOperator("") * init_term

    for i in me_table:

        if i.shape == (5,):
            # two-particle operator
            mb_obs += FermionOperator(
                ((int(i[0]), 1), (int(i[1]), 1), (int(i[2]), 0), (int(i[3]), 0)), i[4]
            )
        elif i.shape == (3,):
            # single-particle operator
            mb_obs += FermionOperator(((int(i[0]), 1), (int(i[1]), 0)), i[2])

    # Map the fermionic operator to a qubit operator
    if mapping.strip().lower() == "bravyi_kitaev":
        return structure.convert_observable(bravyi_kitaev(mb_obs), wires=wires)

    return structure.convert_observable(jordan_wigner(mb_obs), wires=wires)


def spin_z(orbitals, mapping="jordan_wigner", wires=None):
    r"""Computes the total spin projection operator :math:`\hat{S}_z` in the Pauli basis.

    The total spin projection operator :math:`\hat{S}_z` is given by

    .. math::

        \hat{S}_z = \sum_{\alpha, \beta} \langle \alpha \vert \hat{s}_z \vert \beta \rangle
        ~ \hat{c}_\alpha^\dagger \hat{c}_\beta, ~~ \langle \alpha \vert \hat{s}_z
        \vert \beta \rangle = s_{z_\alpha} \delta_{\alpha,\beta},

    where :math:`s_{z_\alpha} = \pm 1/2` is the spin-projection of the single-particle state
    :math:`\vert \alpha \rangle`. The operators :math:`\hat{c}^\dagger` and :math:`\hat{c}`
    are the particle creation and annihilation operators, respectively.

    Args:
        orbitals (str): Number of *spin* orbitals. If an active space is defined, this is
            the number of active spin-orbitals.
        mapping (str): Specifies the transformation to map the fermionic operator to the
            Pauli basis. Input values can be ``'jordan_wigner'`` or ``'bravyi_kitaev'``.
        wires (Wires, list, tuple, dict): Custom wire mapping used to convert the qubit operator
            to an observable measurable in a PennyLane ansatz.
            For types Wires/list/tuple, each item in the iterable represents a wire label
            corresponding to the qubit number equal to its index.
            For type dict, only int-keyed dict (for qubit-to-wire conversion) is accepted.
            If None, will use identity map (e.g. 0->0, 1->1, ...).

    Returns:
        pennylane.Hamiltonian: the total spin projection observable :math:`\hat{S}_z`

    **Example**

    >>> orbitals = 4
    >>> Sz = spin_z(orbitals, mapping="jordan_wigner")
    >>> print(Sz)
    (-0.25) [Z0]
    + (0.25) [Z1]
    + (-0.25) [Z2]
    + (0.25) [Z3]
    """

    if orbitals <= 0:
        raise ValueError(
            "'orbitals' must be greater than 0; got for 'orbitals' {}".format(orbitals)
        )

    r = np.arange(orbitals)
    sz_orb = np.where(np.arange(orbitals) % 2 == 0, 0.5, -0.5)
    table = np.vstack([r, r, sz_orb]).T

    return observable(table, mapping=mapping, wires=wires)


def particle_number(orbitals, mapping="jordan_wigner", wires=None):
    r"""Computes the particle number operator :math:`\hat{N}=\sum_\alpha \hat{n}_\alpha`
    in the Pauli basis.

    The particle number operator is given by

    .. math::

        \hat{N} = \sum_\alpha \hat{c}_\alpha^\dagger \hat{c}_\alpha,

    where the index :math:`\alpha` runs over the basis of single-particle states
    :math:`\vert \alpha \rangle`, and the operators :math:`\hat{c}^\dagger` and :math:`\hat{c}` are
    the particle creation and annihilation operators, respectively.

    Args:
        orbitals (int): Number of *spin* orbitals. If an active space is defined, this is
            the number of active spin-orbitals.
        mapping (str): Specifies the transformation to map the fermionic operator to the
            Pauli basis. Input values can be ``'jordan_wigner'`` or ``'bravyi_kitaev'``.
        wires (Wires, list, tuple, dict): Custom wire mapping used to convert the qubit operator
            to an observable measurable in a PennyLane ansatz.
            For types Wires/list/tuple, each item in the iterable represents a wire label
            corresponding to the qubit number equal to its index.
            For type dict, only int-keyed dict (for qubit-to-wire conversion) is accepted.
            If None, will use identity map (e.g. 0->0, 1->1, ...).

    Returns:
        pennylane.Hamiltonian: the fermionic-to-qubit transformed observable

    **Example**

    >>> orbitals = 4
    >>> N = particle_number(orbitals, mapping="jordan_wigner")
    >>> print(N)
    (2.0) [I0]
    + (-0.5) [Z0]
    + (-0.5) [Z1]
    + (-0.5) [Z2]
    + (-0.5) [Z3]
    >>> N = particle_number(orbitals, mapping="jordan_wigner", wires=['w0','w1','w2','w3'])
    >>> print(N)
    (2.0) [Iw0]
    + (-0.5) [Zw0]
    + (-0.5) [Zw1]
    + (-0.5) [Zw2]
    + (-0.5) [Zw3]
    """

    if orbitals <= 0:
        raise ValueError(
            "'orbitals' must be greater than 0; got for 'orbitals' {}".format(orbitals)
        )

    r = np.arange(orbitals)
    table = np.vstack([r, r, np.ones([orbitals])]).T

    return observable(table, mapping=mapping, wires=wires)


def one_particle(t_me, core=None, active=None, cutoff=1.0e-12):
    r"""Generates the table of  matrix elements of a given one-particle operator
    that can be used to build the many-body observable.

    Second quantized one-particle operators are expanded in the basis of single-particle
    states as

    .. math::

        \hat{T} = \sum_{\alpha, \beta} \langle \alpha \vert \hat{t} \vert \beta \rangle
        [\hat{c}_{\alpha\uparrow}^\dagger \hat{c}_{\beta\uparrow} +
        \hat{c}_{\alpha\downarrow}^\dagger \hat{c}_{\beta\downarrow}].

    In the equation above the indices :math:`\alpha, \beta` run over the basis of spatial
    orbitals :math:`\vert \alpha \rangle = \phi_\alpha(r)`. Notice that the spin quantum numbers
    are accounted for explicitly with the up/down arrows since the operator :math:`t` 
    is assumed to act only on the spatial coordinates. The operators :math:`\hat{c}^\dagger`
    and :math:`\hat{c}` are the particle creation and annihilation operators, respectively.
    :math:`\langle \alpha \vert \hat{t} \vert \beta \rangle` denotes the matrix elements of
    the operator :math:`\hat{t}`

    .. math::

        \langle \alpha \vert \hat{t} \vert \beta \rangle = \int dr ~ \phi_\alpha^*(r)
        \hat{t}(r) \phi_\beta(r).

    If an active space is defined (see :func:`~.active_space`), the indices
    :math:`\alpha, \beta` run over the active orbitals and the contribution due to core
    orbitals, if any, is computed as
    :math:`t_\mathrm{core} = 2 \sum_{\alpha\in \mathrm{core}}  \langle \alpha \vert \hat{t}`.

    Args:
        t_me (array[float]): 2D Numpy array with the matrix elements
            :math:`\langle \alpha \vert \hat{t} \vert \beta \rangle`
        core (list): indices of core orbitals, i.e., the orbitals that are
            not correlated in the many-body wave function
        active (list): indices of active orbitals, i.e., the orbitals used to
            build the correlated many-body wave function
        cutoff (float): Threshold for including the matrix elements in the table. The 
            matrix elements with absolute value less than ``cutoff`` are discarded.
        
    Returns:
        tuple: The table with the matrix elements of the one-particle operator
        and the contribution due to core orbitals. The table is returned as a 2D Numpy
        array where each row contains the two indices of the *spin* orbitals
        and the corresponding value of the matrix element. 

    **Example**

    >>> t_me = np.array([[-4.72739313e+00, -1.05499666e-01, -1.66961416e-01,  6.18014041e-16,
    ...                    2.86964662e-16, -3.46772026e-02],
    ...                  [-1.05499666e-01, -1.49264622e+00, 3.28928073e-02, -2.20398308e-16,
    ...                    1.93277291e-16,  5.27078882e-02],
    ...                  [-1.66961416e-01,  3.28928073e-02, -1.12554473e+00, -2.82912389e-17,
    ...                    2.55224784e-16, -3.04455743e-02],
    ...                  [ 6.18014041e-16, -2.20398308e-16, -2.82912389e-17, -1.13579985e+00,
    ...                   -1.94289029e-16, -2.36158697e-16],
    ...                  [ 2.86964662e-16,  1.93277291e-16,  2.55224784e-16, -2.77555756e-16,
    ...                   -1.13579985e+00,  2.06665432e-16],
    ...                  [-3.46772026e-02,  5.27078882e-02, -3.04455743e-02, -2.36158697e-16,
    ...                    2.06665432e-16, -9.50966595e-01]]

    >>> t_table, t_core = one_particle(t_me, core=[0], active=[1, 2])
    >>> print(t_table)
    [[ 0.          0.         -1.49264622]
     [ 1.          1.         -1.49264622]
     [ 0.          2.          0.03289281]
     [ 1.          3.          0.03289281]
     [ 2.          0.          0.03289281]
     [ 3.          1.          0.03289281]
     [ 2.          2.         -1.12554473]
     [ 3.          3.         -1.12554473]]
    >>> print(t_core)
    -9.45478625532135
    """
   
    orbitals = t_me.shape[0]
    
    if t_me.ndim != 2:
        raise ValueError(
            "'t_me' must be a 2D array; got 't_me.ndim = ' {}".format(t_me.ndim)
        )
    
    if core is None:
        t_core = 0
    else:
        if (True in [i > orbitals or i < 0 for i in core]):
            raise ValueError("Indices of core orbitals must be between 0 and {}".format(orbitals))
            
        # Compute contribution due to core orbitals
        t_core = 0
        for i in core:
            t_core += t_me[i,i]
        t_core = 2*t_core
    
    if active is None:
        if core is None:
            active = list(range(orbitals))
        else:
            active = [i for i in range(orbitals) if i not in core]
            
    if (True in [i > orbitals or i < 0 for i in active]):
        raise ValueError("Indices of active orbitals must be between 0 and {}".format(orbitals))
    
    # Indices of the matrix elements with absolute values >= cutoff
    row, column = np.nonzero(np.abs(t_me) >= cutoff)
    
    # Singling out the indices of active orbitals
    rc_pairs = []
    for i in range(len(row)):
        if row[i] in active and column[i] in active:
            rc_pairs.append([row[i], column[i]])
    
    # Building the table of matrix elements
    t_table = np.zeros((2*len(rc_pairs), 3))
    for i, pair in enumerate(rc_pairs):
        alpha, beta = pair
        element = t_me[alpha, beta] 
        
        # spin-up term
        t_table[2*i,0] = 2*active.index(alpha)
        t_table[2*i,1] = 2*active.index(beta)
        t_table[2*i,2] = element
        
        # spin-down term
        t_table[2*i+1,0] = 2*active.index(alpha) + 1
        t_table[2*i+1,1] = 2*active.index(beta) + 1
        t_table[2*i+1,2] = element
    
    return t_table, t_core


__all__ = [
    "observable",
    "particle_number",
    "spin_z",
    "spin2",
    "one_particle",
    "_spin2_matrix_elements",
]
