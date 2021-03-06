#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import itertools
import numpy as np

from pyspark import SparkContext
from pyspark import since, keyword_only
from pyspark.ml import Estimator, Model
from pyspark.ml.param import Params, Param, TypeConverters
from pyspark.ml.param.shared import HasSeed
from pyspark.ml.util import JavaMLWriter, JavaMLReader, MLReadable, MLWritable
from pyspark.ml.wrapper import JavaParams
from pyspark.sql.functions import rand
from pyspark.mllib.common import inherit_doc, _py2java

__all__ = ['ParamGridBuilder', 'CrossValidator', 'CrossValidatorModel', 'TrainValidationSplit',
           'TrainValidationSplitModel']


class ParamGridBuilder(object):
    r"""
    Builder for a param grid used in grid search-based model selection.

    >>> from pyspark.ml.classification import LogisticRegression
    >>> lr = LogisticRegression()
    >>> output = ParamGridBuilder() \
    ...     .baseOn({lr.labelCol: 'l'}) \
    ...     .baseOn([lr.predictionCol, 'p']) \
    ...     .addGrid(lr.regParam, [1.0, 2.0]) \
    ...     .addGrid(lr.maxIter, [1, 5]) \
    ...     .build()
    >>> expected = [
    ...     {lr.regParam: 1.0, lr.maxIter: 1, lr.labelCol: 'l', lr.predictionCol: 'p'},
    ...     {lr.regParam: 2.0, lr.maxIter: 1, lr.labelCol: 'l', lr.predictionCol: 'p'},
    ...     {lr.regParam: 1.0, lr.maxIter: 5, lr.labelCol: 'l', lr.predictionCol: 'p'},
    ...     {lr.regParam: 2.0, lr.maxIter: 5, lr.labelCol: 'l', lr.predictionCol: 'p'}]
    >>> len(output) == len(expected)
    True
    >>> all([m in expected for m in output])
    True

    .. versionadded:: 1.4.0
    """

    def __init__(self):
        self._param_grid = {}

    @since("1.4.0")
    def addGrid(self, param, values):
        """
        Sets the given parameters in this grid to fixed values.
        """
        self._param_grid[param] = values

        return self

    @since("1.4.0")
    def baseOn(self, *args):
        """
        Sets the given parameters in this grid to fixed values.
        Accepts either a parameter dictionary or a list of (parameter, value) pairs.
        """
        if isinstance(args[0], dict):
            self.baseOn(*args[0].items())
        else:
            for (param, value) in args:
                self.addGrid(param, [value])

        return self

    @since("1.4.0")
    def build(self):
        """
        Builds and returns all combinations of parameters specified
        by the param grid.
        """
        keys = self._param_grid.keys()
        grid_values = self._param_grid.values()
        return [dict(zip(keys, prod)) for prod in itertools.product(*grid_values)]


class ValidatorParams(HasSeed):
    """
    Common params for TrainValidationSplit and CrossValidator.
    """

    estimator = Param(Params._dummy(), "estimator", "estimator to be cross-validated")
    estimatorParamMaps = Param(Params._dummy(), "estimatorParamMaps", "estimator param maps")
    evaluator = Param(
        Params._dummy(), "evaluator",
        "evaluator used to select hyper-parameters that maximize the validator metric")

    def setEstimator(self, value):
        """
        Sets the value of :py:attr:`estimator`.
        """
        return self._set(estimator=value)

    def getEstimator(self):
        """
        Gets the value of estimator or its default value.
        """
        return self.getOrDefault(self.estimator)

    def setEstimatorParamMaps(self, value):
        """
        Sets the value of :py:attr:`estimatorParamMaps`.
        """
        return self._set(estimatorParamMaps=value)

    def getEstimatorParamMaps(self):
        """
        Gets the value of estimatorParamMaps or its default value.
        """
        return self.getOrDefault(self.estimatorParamMaps)

    def setEvaluator(self, value):
        """
        Sets the value of :py:attr:`evaluator`.
        """
        return self._set(evaluator=value)

    def getEvaluator(self):
        """
        Gets the value of evaluator or its default value.
        """
        return self.getOrDefault(self.evaluator)

    @classmethod
    def _from_java_impl(cls, java_stage):
        """
        Return Python estimator, estimatorParamMaps, and evaluator from a Java ValidatorParams.
        """

        # Load information from java_stage to the instance.
        estimator = JavaParams._from_java(java_stage.getEstimator())
        evaluator = JavaParams._from_java(java_stage.getEvaluator())
        epms = [estimator._transfer_param_map_from_java(epm)
                for epm in java_stage.getEstimatorParamMaps()]
        return estimator, epms, evaluator

    def _to_java_impl(self):
        """
        Return Java estimator, estimatorParamMaps, and evaluator from this Python instance.
        """

        gateway = SparkContext._gateway
        cls = SparkContext._jvm.org.apache.spark.ml.param.ParamMap

        java_epms = gateway.new_array(cls, len(self.getEstimatorParamMaps()))
        for idx, epm in enumerate(self.getEstimatorParamMaps()):
            java_epms[idx] = self.getEstimator()._transfer_param_map_to_java(epm)

        java_estimator = self.getEstimator()._to_java()
        java_evaluator = self.getEvaluator()._to_java()
        return java_estimator, java_epms, java_evaluator


class CrossValidator(Estimator, ValidatorParams, MLReadable, MLWritable):
    """
    K-fold cross validation.

    >>> from pyspark.ml.classification import LogisticRegression
    >>> from pyspark.ml.evaluation import BinaryClassificationEvaluator
    >>> from pyspark.mllib.linalg import Vectors
    >>> dataset = sqlContext.createDataFrame(
    ...     [(Vectors.dense([0.0]), 0.0),
    ...      (Vectors.dense([0.4]), 1.0),
    ...      (Vectors.dense([0.5]), 0.0),
    ...      (Vectors.dense([0.6]), 1.0),
    ...      (Vectors.dense([1.0]), 1.0)] * 10,
    ...     ["features", "label"])
    >>> lr = LogisticRegression()
    >>> grid = ParamGridBuilder().addGrid(lr.maxIter, [0, 1]).build()
    >>> evaluator = BinaryClassificationEvaluator()
    >>> cv = CrossValidator(estimator=lr, estimatorParamMaps=grid, evaluator=evaluator)
    >>> cvModel = cv.fit(dataset)
    >>> evaluator.evaluate(cvModel.transform(dataset))
    0.8333...

    .. versionadded:: 1.4.0
    """

    numFolds = Param(Params._dummy(), "numFolds", "number of folds for cross validation",
                     typeConverter=TypeConverters.toInt)

    @keyword_only
    def __init__(self, estimator=None, estimatorParamMaps=None, evaluator=None, numFolds=3,
                 seed=None):
        """
        __init__(self, estimator=None, estimatorParamMaps=None, evaluator=None, numFolds=3,\
                 seed=None)
        """
        super(CrossValidator, self).__init__()
        self._setDefault(numFolds=3)
        kwargs = self.__init__._input_kwargs
        self._set(**kwargs)

    @keyword_only
    @since("1.4.0")
    def setParams(self, estimator=None, estimatorParamMaps=None, evaluator=None, numFolds=3,
                  seed=None):
        """
        setParams(self, estimator=None, estimatorParamMaps=None, evaluator=None, numFolds=3,\
                  seed=None):
        Sets params for cross validator.
        """
        kwargs = self.setParams._input_kwargs
        return self._set(**kwargs)

    @since("1.4.0")
    def setNumFolds(self, value):
        """
        Sets the value of :py:attr:`numFolds`.
        """
        self._set(numFolds=value)
        return self

    @since("1.4.0")
    def getNumFolds(self):
        """
        Gets the value of numFolds or its default value.
        """
        return self.getOrDefault(self.numFolds)

    def _fit(self, dataset):
        est = self.getOrDefault(self.estimator)
        epm = self.getOrDefault(self.estimatorParamMaps)
        numModels = len(epm)
        eva = self.getOrDefault(self.evaluator)
        nFolds = self.getOrDefault(self.numFolds)
        seed = self.getOrDefault(self.seed)
        h = 1.0 / nFolds
        randCol = self.uid + "_rand"
        df = dataset.select("*", rand(seed).alias(randCol))
        metrics = np.zeros(numModels)
        for i in range(nFolds):
            validateLB = i * h
            validateUB = (i + 1) * h
            condition = (df[randCol] >= validateLB) & (df[randCol] < validateUB)
            validation = df.filter(condition)
            train = df.filter(~condition)
            for j in range(numModels):
                model = est.fit(train, epm[j])
                # TODO: duplicate evaluator to take extra params from input
                metric = eva.evaluate(model.transform(validation, epm[j]))
                metrics[j] += metric

        if eva.isLargerBetter():
            bestIndex = np.argmax(metrics)
        else:
            bestIndex = np.argmin(metrics)
        bestModel = est.fit(dataset, epm[bestIndex])
        return self._copyValues(CrossValidatorModel(bestModel))

    @since("1.4.0")
    def copy(self, extra=None):
        """
        Creates a copy of this instance with a randomly generated uid
        and some extra params. This copies creates a deep copy of
        the embedded paramMap, and copies the embedded and extra parameters over.

        :param extra: Extra parameters to copy to the new instance
        :return: Copy of this instance
        """
        if extra is None:
            extra = dict()
        newCV = Params.copy(self, extra)
        if self.isSet(self.estimator):
            newCV.setEstimator(self.getEstimator().copy(extra))
        # estimatorParamMaps remain the same
        if self.isSet(self.evaluator):
            newCV.setEvaluator(self.getEvaluator().copy(extra))
        return newCV

    @since("2.0.0")
    def write(self):
        """Returns an MLWriter instance for this ML instance."""
        return JavaMLWriter(self)

    @since("2.0.0")
    def save(self, path):
        """Save this ML instance to the given path, a shortcut of `write().save(path)`."""
        self.write().save(path)

    @classmethod
    @since("2.0.0")
    def read(cls):
        """Returns an MLReader instance for this class."""
        return JavaMLReader(cls)

    @classmethod
    def _from_java(cls, java_stage):
        """
        Given a Java CrossValidator, create and return a Python wrapper of it.
        Used for ML persistence.
        """

        estimator, epms, evaluator = super(CrossValidator, cls)._from_java_impl(java_stage)
        numFolds = java_stage.getNumFolds()
        seed = java_stage.getSeed()
        # Create a new instance of this stage.
        py_stage = cls(estimator=estimator, estimatorParamMaps=epms, evaluator=evaluator,
                       numFolds=numFolds, seed=seed)
        py_stage._resetUid(java_stage.uid())
        return py_stage

    def _to_java(self):
        """
        Transfer this instance to a Java CrossValidator. Used for ML persistence.

        :return: Java object equivalent to this instance.
        """

        estimator, epms, evaluator = super(CrossValidator, self)._to_java_impl()

        _java_obj = JavaParams._new_java_obj("org.apache.spark.ml.tuning.CrossValidator", self.uid)
        _java_obj.setEstimatorParamMaps(epms)
        _java_obj.setEvaluator(evaluator)
        _java_obj.setEstimator(estimator)
        _java_obj.setSeed(self.getSeed())
        _java_obj.setNumFolds(self.getNumFolds())

        return _java_obj


class CrossValidatorModel(Model, ValidatorParams, MLReadable, MLWritable):
    """
    Model from k-fold cross validation.

    .. versionadded:: 1.4.0
    """

    def __init__(self, bestModel):
        super(CrossValidatorModel, self).__init__()
        #: best model from cross validation
        self.bestModel = bestModel

    def _transform(self, dataset):
        return self.bestModel.transform(dataset)

    @since("1.4.0")
    def copy(self, extra=None):
        """
        Creates a copy of this instance with a randomly generated uid
        and some extra params. This copies the underlying bestModel,
        creates a deep copy of the embedded paramMap, and
        copies the embedded and extra parameters over.

        :param extra: Extra parameters to copy to the new instance
        :return: Copy of this instance
        """
        if extra is None:
            extra = dict()
        return CrossValidatorModel(self.bestModel.copy(extra))

    @since("2.0.0")
    def write(self):
        """Returns an MLWriter instance for this ML instance."""
        return JavaMLWriter(self)

    @since("2.0.0")
    def save(self, path):
        """Save this ML instance to the given path, a shortcut of `write().save(path)`."""
        self.write().save(path)

    @classmethod
    @since("2.0.0")
    def read(cls):
        """Returns an MLReader instance for this class."""
        return JavaMLReader(cls)

    @classmethod
    def _from_java(cls, java_stage):
        """
        Given a Java CrossValidatorModel, create and return a Python wrapper of it.
        Used for ML persistence.
        """

        # Load information from java_stage to the instance.
        bestModel = JavaParams._from_java(java_stage.bestModel())
        estimator, epms, evaluator = super(CrossValidatorModel, cls)._from_java_impl(java_stage)
        # Create a new instance of this stage.
        py_stage = cls(bestModel=bestModel)\
            .setEstimator(estimator).setEstimatorParamMaps(epms).setEvaluator(evaluator)
        py_stage._resetUid(java_stage.uid())
        return py_stage

    def _to_java(self):
        """
        Transfer this instance to a Java CrossValidatorModel. Used for ML persistence.

        :return: Java object equivalent to this instance.
        """

        sc = SparkContext._active_spark_context

        _java_obj = JavaParams._new_java_obj("org.apache.spark.ml.tuning.CrossValidatorModel",
                                             self.uid,
                                             self.bestModel._to_java(),
                                             _py2java(sc, []))
        estimator, epms, evaluator = super(CrossValidatorModel, self)._to_java_impl()

        _java_obj.set("evaluator", evaluator)
        _java_obj.set("estimator", estimator)
        _java_obj.set("estimatorParamMaps", epms)
        return _java_obj


class TrainValidationSplit(Estimator, ValidatorParams, MLReadable, MLWritable):
    """
    Train-Validation-Split.

    >>> from pyspark.ml.classification import LogisticRegression
    >>> from pyspark.ml.evaluation import BinaryClassificationEvaluator
    >>> from pyspark.mllib.linalg import Vectors
    >>> dataset = sqlContext.createDataFrame(
    ...     [(Vectors.dense([0.0]), 0.0),
    ...      (Vectors.dense([0.4]), 1.0),
    ...      (Vectors.dense([0.5]), 0.0),
    ...      (Vectors.dense([0.6]), 1.0),
    ...      (Vectors.dense([1.0]), 1.0)] * 10,
    ...     ["features", "label"])
    >>> lr = LogisticRegression()
    >>> grid = ParamGridBuilder().addGrid(lr.maxIter, [0, 1]).build()
    >>> evaluator = BinaryClassificationEvaluator()
    >>> tvs = TrainValidationSplit(estimator=lr, estimatorParamMaps=grid, evaluator=evaluator)
    >>> tvsModel = tvs.fit(dataset)
    >>> evaluator.evaluate(tvsModel.transform(dataset))
    0.8333...

    .. versionadded:: 2.0.0
    """

    trainRatio = Param(Params._dummy(), "trainRatio", "Param for ratio between train and\
     validation data. Must be between 0 and 1.", typeConverter=TypeConverters.toFloat)

    @keyword_only
    def __init__(self, estimator=None, estimatorParamMaps=None, evaluator=None, trainRatio=0.75,
                 seed=None):
        """
        __init__(self, estimator=None, estimatorParamMaps=None, evaluator=None, trainRatio=0.75,\
                 seed=None)
        """
        super(TrainValidationSplit, self).__init__()
        self._setDefault(trainRatio=0.75)
        kwargs = self.__init__._input_kwargs
        self._set(**kwargs)

    @since("2.0.0")
    @keyword_only
    def setParams(self, estimator=None, estimatorParamMaps=None, evaluator=None, trainRatio=0.75,
                  seed=None):
        """
        setParams(self, estimator=None, estimatorParamMaps=None, evaluator=None, trainRatio=0.75,\
                  seed=None):
        Sets params for the train validation split.
        """
        kwargs = self.setParams._input_kwargs
        return self._set(**kwargs)

    @since("2.0.0")
    def setTrainRatio(self, value):
        """
        Sets the value of :py:attr:`trainRatio`.
        """
        self._set(trainRatio=value)
        return self

    @since("2.0.0")
    def getTrainRatio(self):
        """
        Gets the value of trainRatio or its default value.
        """
        return self.getOrDefault(self.trainRatio)

    def _fit(self, dataset):
        est = self.getOrDefault(self.estimator)
        epm = self.getOrDefault(self.estimatorParamMaps)
        numModels = len(epm)
        eva = self.getOrDefault(self.evaluator)
        tRatio = self.getOrDefault(self.trainRatio)
        seed = self.getOrDefault(self.seed)
        randCol = self.uid + "_rand"
        df = dataset.select("*", rand(seed).alias(randCol))
        metrics = np.zeros(numModels)
        condition = (df[randCol] >= tRatio)
        validation = df.filter(condition)
        train = df.filter(~condition)
        for j in range(numModels):
            model = est.fit(train, epm[j])
            metric = eva.evaluate(model.transform(validation, epm[j]))
            metrics[j] += metric
        if eva.isLargerBetter():
            bestIndex = np.argmax(metrics)
        else:
            bestIndex = np.argmin(metrics)
        bestModel = est.fit(dataset, epm[bestIndex])
        return self._copyValues(TrainValidationSplitModel(bestModel))

    @since("2.0.0")
    def copy(self, extra=None):
        """
        Creates a copy of this instance with a randomly generated uid
        and some extra params. This copies creates a deep copy of
        the embedded paramMap, and copies the embedded and extra parameters over.

        :param extra: Extra parameters to copy to the new instance
        :return: Copy of this instance
        """
        if extra is None:
            extra = dict()
        newTVS = Params.copy(self, extra)
        if self.isSet(self.estimator):
            newTVS.setEstimator(self.getEstimator().copy(extra))
        # estimatorParamMaps remain the same
        if self.isSet(self.evaluator):
            newTVS.setEvaluator(self.getEvaluator().copy(extra))
        return newTVS

    @since("2.0.0")
    def write(self):
        """Returns an MLWriter instance for this ML instance."""
        return JavaMLWriter(self)

    @since("2.0.0")
    def save(self, path):
        """Save this ML instance to the given path, a shortcut of `write().save(path)`."""
        self.write().save(path)

    @classmethod
    @since("2.0.0")
    def read(cls):
        """Returns an MLReader instance for this class."""
        return JavaMLReader(cls)

    @classmethod
    def _from_java(cls, java_stage):
        """
        Given a Java TrainValidationSplit, create and return a Python wrapper of it.
        Used for ML persistence.
        """

        estimator, epms, evaluator = super(TrainValidationSplit, cls)._from_java_impl(java_stage)
        trainRatio = java_stage.getTrainRatio()
        seed = java_stage.getSeed()
        # Create a new instance of this stage.
        py_stage = cls(estimator=estimator, estimatorParamMaps=epms, evaluator=evaluator,
                       trainRatio=trainRatio, seed=seed)
        py_stage._resetUid(java_stage.uid())
        return py_stage

    def _to_java(self):
        """
        Transfer this instance to a Java TrainValidationSplit. Used for ML persistence.

        :return: Java object equivalent to this instance.
        """

        estimator, epms, evaluator = super(TrainValidationSplit, self)._to_java_impl()

        _java_obj = JavaParams._new_java_obj("org.apache.spark.ml.tuning.TrainValidationSplit",
                                             self.uid)
        _java_obj.setEstimatorParamMaps(epms)
        _java_obj.setEvaluator(evaluator)
        _java_obj.setEstimator(estimator)
        _java_obj.setTrainRatio(self.getTrainRatio())
        _java_obj.setSeed(self.getSeed())

        return _java_obj


class TrainValidationSplitModel(Model, ValidatorParams, MLReadable, MLWritable):
    """
    Model from train validation split.

    .. versionadded:: 2.0.0
    """

    def __init__(self, bestModel):
        super(TrainValidationSplitModel, self).__init__()
        #: best model from cross validation
        self.bestModel = bestModel

    def _transform(self, dataset):
        return self.bestModel.transform(dataset)

    @since("2.0.0")
    def copy(self, extra=None):
        """
        Creates a copy of this instance with a randomly generated uid
        and some extra params. This copies the underlying bestModel,
        creates a deep copy of the embedded paramMap, and
        copies the embedded and extra parameters over.

        :param extra: Extra parameters to copy to the new instance
        :return: Copy of this instance
        """
        if extra is None:
            extra = dict()
        return TrainValidationSplitModel(self.bestModel.copy(extra))

    @since("2.0.0")
    def write(self):
        """Returns an MLWriter instance for this ML instance."""
        return JavaMLWriter(self)

    @since("2.0.0")
    def save(self, path):
        """Save this ML instance to the given path, a shortcut of `write().save(path)`."""
        self.write().save(path)

    @classmethod
    @since("2.0.0")
    def read(cls):
        """Returns an MLReader instance for this class."""
        return JavaMLReader(cls)

    @classmethod
    def _from_java(cls, java_stage):
        """
        Given a Java TrainValidationSplitModel, create and return a Python wrapper of it.
        Used for ML persistence.
        """

        # Load information from java_stage to the instance.
        bestModel = JavaParams._from_java(java_stage.bestModel())
        estimator, epms, evaluator = \
            super(TrainValidationSplitModel, cls)._from_java_impl(java_stage)
        # Create a new instance of this stage.
        py_stage = cls(bestModel=bestModel)\
            .setEstimator(estimator).setEstimatorParamMaps(epms).setEvaluator(evaluator)
        py_stage._resetUid(java_stage.uid())
        return py_stage

    def _to_java(self):
        """
        Transfer this instance to a Java TrainValidationSplitModel. Used for ML persistence.

        :return: Java object equivalent to this instance.
        """

        sc = SparkContext._active_spark_context

        _java_obj = JavaParams._new_java_obj(
            "org.apache.spark.ml.tuning.TrainValidationSplitModel",
            self.uid,
            self.bestModel._to_java(),
            _py2java(sc, []))
        estimator, epms, evaluator = super(TrainValidationSplitModel, self)._to_java_impl()

        _java_obj.set("evaluator", evaluator)
        _java_obj.set("estimator", estimator)
        _java_obj.set("estimatorParamMaps", epms)
        return _java_obj


if __name__ == "__main__":
    import doctest

    from pyspark.context import SparkContext
    from pyspark.sql import SQLContext
    globs = globals().copy()

    # The small batch size here ensures that we see multiple batches,
    # even in these small test examples:
    sc = SparkContext("local[2]", "ml.tuning tests")
    sqlContext = SQLContext(sc)
    globs['sc'] = sc
    globs['sqlContext'] = sqlContext
    (failure_count, test_count) = doctest.testmod(globs=globs, optionflags=doctest.ELLIPSIS)
    sc.stop()
    if failure_count:
        exit(-1)
