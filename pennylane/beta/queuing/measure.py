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
# pylint: disable=protected-access
"""
This module contains the functions for computing different types of measurement
outcomes from quantum observables - expectation values, variances of expectations,
and measurement samples using AnnotatedQueues.
"""
import numpy as np

import pennylane as qml
from pennylane.operation import Expectation, Observable, Probability, Sample, Variance
from pennylane.qnodes import QuantumFunctionError


from .queuing import QueuingContext


class MeasurementProcess:
    """Represents a measurement process occurring at the end of a
    quantum variational circuit.

    Args:
        return_type (.ObservableReturnTypes): The type of measurement process.
            This includes ``Expectation``, ``Variance``, ``Sample``, or ``Probability``.
        obs (.Observable): The observable that is to be measured as part of the
            measurement process. Not all measurement processes require observables (for
            example ``Probability``); this argument is optional.
        wires (.Wires): The wires the measurement process applies to.
            This can only be specified if an observable was not provided.
        eigvals (array): A flat array representing the eigenvalues of the measurement.
            This can only be specified if an observable was not provided.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, return_type, obs=None, wires=None, eigvals=None):
        self.return_type = return_type
        self.obs = obs

        self._wires = None
        self._eigvals = None

        if eigvals is not None:
            if obs is not None:
                raise ValueError("Cannot set the eigenvalues if an observable is provided.")

            self._eigvals = np.array(eigvals)

        if wires is not None:
            if obs is not None:
                raise ValueError("Cannot set the wires if an observable is provided.")

            self._wires = wires

        # TODO: remove the following lines once devices
        # have been refactored to accept and understand recieving
        # measurement processes rather than specific observables.

        # The following lines are only applicable for measurement processes
        # that do no have corresponding observables (e.g., Probability). We use
        # them to 'trick' the device into thinking it has recieved an observable.

        # Below, we imitate an identity observable, so that the
        # device undertakes no action upon recieving this observable.
        self.name = "Identity"
        self.diagonalizing_gates = lambda: []
        self.data = []

        # Queue the measurement process
        self.queue()

    @property
    def wires(self):
        r"""The wires the measurement process acts on."""
        if self.obs is not None:
            return self.obs.wires
        return self._wires

    @property
    def eigvals(self):
        r"""Eigenvalues associated with the measurement process.

        If the measurement process has an associated observable,
        the eigenvalues will correspond to this observable. Otherwise,
        they will be the eigenvalues provided when the measurement
        process was instantiated.

        Note that the eigenvalues are not guaranteed to be in any
        particular order.

        **Example:**

        >>> m = MeasurementProcess(Expectation, obs=qml.PauliX(wires=1))
        >>> U.eigvals
        >>> array([1, -1])

        Returns:
            array: eigvals representation
        """
        if self.obs is not None:
            try:
                return self.obs.eigvals
            except NotImplementedError:
                pass

        return self._eigvals

    def expand(self):
        """Expand the measurement of an observable to a unitary
        rotation and a measurement in the computational basis.

        Returns:
            .QuantumTape: a quantum tape containing the operations
            required to diagonalize the observable

        **Example**

        Consider a measurement process consisting of the expectation
        value of an Hermitian observable:

        >>> H = np.array([[1, 2], [2, 4]])
        >>> obs = qml.Hermitian(H, wires=['a'])
        >>> m = MeasurementProcess(Expectation, obs=obs)

        Expanding this out:

        >>> tape = m.expand()

        We can see that the resulting tape has the qubit unitary applied,
        and a measurement process with no observable, but the eigenvalues
        specified:

        >>> print(tape.operations)
        [QubitUnitary(array([[-0.89442719,  0.4472136 ],
              [ 0.4472136 ,  0.89442719]]), wires=['a'])]
        >>> print(tape.measurements[0].eigvals)
        [0. 5.]
        >>> print(tape.measurements[0].obs)
        None
        """
        if self.obs is None:
            raise NotImplementedError("Cannot expand a measurement process with no observable.")

        from pennylane.beta.tapes import QuantumTape  # pylint: disable=import-outside-toplevel

        with QuantumTape() as tape:
            self.obs.diagonalizing_gates()
            MeasurementProcess(self.return_type, wires=self.obs.wires, eigvals=self.obs.eigvals)

        return tape

    def queue(self):
        """Append the measurement process to an annotated queue."""
        if self.obs is not None:
            QueuingContext.update_info(self.obs, owner=self)
            QueuingContext.append(self, owns=self.obs)
        else:
            QueuingContext.append(self)


def expval(op):
    r"""Expectation value of the supplied observable.

    **Example:**

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2)

        @qml.qnode(dev)
        def circuit(x):
            qml.RX(x, wires=0)
            qml.Hadamard(wires=1)
            qml.CNOT(wires=[0, 1])
            return qml.expval(qml.PauliY(0))

    Executing this QNode:

    >>> circuit(0.5)
    -0.4794255386042029

    Args:
        op (Observable): a quantum observable object

    Raises:
        QuantumFunctionError: `op` is not an instance of :class:`~.Observable`
    """
    if not isinstance(op, Observable):
        raise QuantumFunctionError(
            "{} is not an observable: cannot be used with expval".format(op.name)
        )

    return MeasurementProcess(Expectation, obs=op)


def var(op):
    r"""Variance of the supplied observable.

    **Example:**

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2)

        @qml.qnode(dev)
        def circuit(x):
            qml.RX(x, wires=0)
            qml.Hadamard(wires=1)
            qml.CNOT(wires=[0, 1])
            return qml.var(qml.PauliY(0))

    Executing this QNode:

    >>> circuit(0.5)
    0.7701511529340698

    Args:
        op (Observable): a quantum observable object

    Raises:
        QuantumFunctionError: `op` is not an instance of :class:`~.Observable`
    """
    if not isinstance(op, Observable):
        raise QuantumFunctionError(
            "{} is not an observable: cannot be used with var".format(op.name)
        )

    return MeasurementProcess(Variance, obs=op)


def sample(op):
    r"""Sample from the supplied observable, with the number of shots
    determined from the ``dev.shots`` attribute of the corresponding device.

    **Example:**

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2, shots=4)

        @qml.qnode(dev)
        def circuit(x):
            qml.RX(x, wires=0)
            qml.Hadamard(wires=1)
            qml.CNOT(wires=[0, 1])
            return qml.sample(qml.PauliY(0))

    Executing this QNode:

    >>> circuit(0.5)
    array([ 1.,  1.,  1., -1.])

    Args:
        op (Observable): a quantum observable object

    Raises:
        QuantumFunctionError: `op` is not an instance of :class:`~.Observable`
    """
    if not isinstance(op, Observable):
        raise QuantumFunctionError(
            "{} is not an observable: cannot be used with sample".format(op.name)
        )

    return MeasurementProcess(Sample, obs=op)


def probs(wires):
    r"""Probability of each computational basis state.

    This measurement function accepts no observables, and instead
    instructs the QNode to return a flat array containing the
    probabilities of each quantum state.

    Marginal probabilities may also be requested by restricting
    the wires to a subset of the full system; the size of the
    returned array will be ``[2**len(wires)]``.

    **Example:**

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2)

        @qml.qnode(dev)
        def circuit():
            qml.Hadamard(wires=1)
            return qml.probs(wires=[0, 1])

    Executing this QNode:

    >>> circuit()
    array([0.5, 0.5, 0. , 0. ])

    The returned array is in lexicographic order, so corresponds
    to a :math:`50\%` chance of measuring either :math:`|00\rangle`
    or :math:`|01\rangle`.

    Args:
        wires (Sequence[int] or int): the wire the operation acts on
    """
    # pylint: disable=protected-access
    return MeasurementProcess(Probability, wires=qml.wires.Wires(wires))
