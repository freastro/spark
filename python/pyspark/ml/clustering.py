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

from pyspark import since, keyword_only
from pyspark.ml.util import *
from pyspark.ml.wrapper import JavaEstimator, JavaModel
from pyspark.ml.param.shared import *
from pyspark.mllib.common import inherit_doc

__all__ = ['BisectingKMeans', 'BisectingKMeansModel',
           'KMeans', 'KMeansModel',
           'GaussianMixture', 'GaussianMixtureModel']


class GaussianMixtureModel(JavaModel, JavaMLWritable, JavaMLReadable):
    """
    .. note:: Experimental

    Model fitted by GaussianMixture.

    .. versionadded:: 2.0.0
    """

    @property
    @since("2.0.0")
    def weights(self):
        """
        Weight for each Gaussian distribution in the mixture.
        This is a multinomial probability distribution over the k Gaussians,
        where weights[i] is the weight for Gaussian i, and weights sum to 1.
        """
        return self._call_java("weights")

    @property
    @since("2.0.0")
    def gaussiansDF(self):
        """
        Retrieve Gaussian distributions as a DataFrame.
        Each row represents a Gaussian Distribution.
        The DataFrame has two columns: mean (Vector) and cov (Matrix).
        """
        return self._call_java("gaussiansDF")


@inherit_doc
class GaussianMixture(JavaEstimator, HasFeaturesCol, HasPredictionCol, HasMaxIter, HasTol, HasSeed,
                      HasProbabilityCol, JavaMLWritable, JavaMLReadable):
    """
    .. note:: Experimental

    GaussianMixture clustering.

    >>> from pyspark.mllib.linalg import Vectors

    >>> data = [(Vectors.dense([-0.1, -0.05 ]),),
    ...         (Vectors.dense([-0.01, -0.1]),),
    ...         (Vectors.dense([0.9, 0.8]),),
    ...         (Vectors.dense([0.75, 0.935]),),
    ...         (Vectors.dense([-0.83, -0.68]),),
    ...         (Vectors.dense([-0.91, -0.76]),)]
    >>> df = sqlContext.createDataFrame(data, ["features"])
    >>> gm = GaussianMixture(k=3, tol=0.0001,
    ...                      maxIter=10, seed=10)
    >>> model = gm.fit(df)
    >>> weights = model.weights
    >>> len(weights)
    3
    >>> model.gaussiansDF.show()
    +--------------------+--------------------+
    |                mean|                 cov|
    +--------------------+--------------------+
    |[-0.0550000000000...|0.002025000000000...|
    |[0.82499999999999...|0.005625000000000...|
    |[-0.87,-0.7200000...|0.001600000000000...|
    +--------------------+--------------------+
    ...
    >>> transformed = model.transform(df).select("features", "prediction")
    >>> rows = transformed.collect()
    >>> rows[4].prediction == rows[5].prediction
    True
    >>> rows[2].prediction == rows[3].prediction
    True
    >>> gmm_path = temp_path + "/gmm"
    >>> gm.save(gmm_path)
    >>> gm2 = GaussianMixture.load(gmm_path)
    >>> gm2.getK()
    3
    >>> model_path = temp_path + "/gmm_model"
    >>> model.save(model_path)
    >>> model2 = GaussianMixtureModel.load(model_path)
    >>> model2.weights == model.weights
    True
    >>> model2.gaussiansDF.show()
    +--------------------+--------------------+
    |                mean|                 cov|
    +--------------------+--------------------+
    |[-0.0550000000000...|0.002025000000000...|
    |[0.82499999999999...|0.005625000000000...|
    |[-0.87,-0.7200000...|0.001600000000000...|
    +--------------------+--------------------+
    ...

    .. versionadded:: 2.0.0
    """

    k = Param(Params._dummy(), "k", "number of clusters to create",
              typeConverter=TypeConverters.toInt)

    @keyword_only
    def __init__(self, featuresCol="features", predictionCol="prediction", k=2,
                 probabilityCol="probability", tol=0.01, maxIter=100, seed=None):
        """
        __init__(self, featuresCol="features", predictionCol="prediction", k=2, \
                 probabilityCol="probability", tol=0.01, maxIter=100, seed=None)
        """
        super(GaussianMixture, self).__init__()
        self._java_obj = self._new_java_obj("org.apache.spark.ml.clustering.GaussianMixture",
                                            self.uid)
        self._setDefault(k=2, tol=0.01, maxIter=100)
        kwargs = self.__init__._input_kwargs
        self.setParams(**kwargs)

    def _create_model(self, java_model):
        return GaussianMixtureModel(java_model)

    @keyword_only
    @since("2.0.0")
    def setParams(self, featuresCol="features", predictionCol="prediction", k=2,
                  probabilityCol="probability", tol=0.01, maxIter=100, seed=None):
        """
        setParams(self, featuresCol="features", predictionCol="prediction", k=2, \
                  probabilityCol="probability", tol=0.01, maxIter=100, seed=None)

        Sets params for GaussianMixture.
        """
        kwargs = self.setParams._input_kwargs
        return self._set(**kwargs)

    @since("2.0.0")
    def setK(self, value):
        """
        Sets the value of :py:attr:`k`.
        """
        self._set(k=value)
        return self

    @since("2.0.0")
    def getK(self):
        """
        Gets the value of `k`
        """
        return self.getOrDefault(self.k)


class KMeansModel(JavaModel, JavaMLWritable, JavaMLReadable):
    """
    Model fitted by KMeans.

    .. versionadded:: 1.5.0
    """

    @since("1.5.0")
    def clusterCenters(self):
        """Get the cluster centers, represented as a list of NumPy arrays."""
        return [c.toArray() for c in self._call_java("clusterCenters")]

    @since("2.0.0")
    def computeCost(self, dataset):
        """
        Return the K-means cost (sum of squared distances of points to their nearest center)
        for this model on the given data.
        """
        return self._call_java("computeCost", dataset)


@inherit_doc
class KMeans(JavaEstimator, HasFeaturesCol, HasPredictionCol, HasMaxIter, HasTol, HasSeed,
             JavaMLWritable, JavaMLReadable):
    """
    K-means clustering with a k-means++ like initialization mode
    (the k-means|| algorithm by Bahmani et al).

    >>> from pyspark.mllib.linalg import Vectors
    >>> data = [(Vectors.dense([0.0, 0.0]),), (Vectors.dense([1.0, 1.0]),),
    ...         (Vectors.dense([9.0, 8.0]),), (Vectors.dense([8.0, 9.0]),)]
    >>> df = sqlContext.createDataFrame(data, ["features"])
    >>> kmeans = KMeans(k=2, seed=1)
    >>> model = kmeans.fit(df)
    >>> centers = model.clusterCenters()
    >>> len(centers)
    2
    >>> model.computeCost(df)
    2.000...
    >>> transformed = model.transform(df).select("features", "prediction")
    >>> rows = transformed.collect()
    >>> rows[0].prediction == rows[1].prediction
    True
    >>> rows[2].prediction == rows[3].prediction
    True
    >>> kmeans_path = temp_path + "/kmeans"
    >>> kmeans.save(kmeans_path)
    >>> kmeans2 = KMeans.load(kmeans_path)
    >>> kmeans2.getK()
    2
    >>> model_path = temp_path + "/kmeans_model"
    >>> model.save(model_path)
    >>> model2 = KMeansModel.load(model_path)
    >>> model.clusterCenters()[0] == model2.clusterCenters()[0]
    array([ True,  True], dtype=bool)
    >>> model.clusterCenters()[1] == model2.clusterCenters()[1]
    array([ True,  True], dtype=bool)

    .. versionadded:: 1.5.0
    """

    k = Param(Params._dummy(), "k", "number of clusters to create",
              typeConverter=TypeConverters.toInt)
    initMode = Param(Params._dummy(), "initMode",
                     "the initialization algorithm. This can be either \"random\" to " +
                     "choose random points as initial cluster centers, or \"k-means||\" " +
                     "to use a parallel variant of k-means++",
                     typeConverter=TypeConverters.toString)
    initSteps = Param(Params._dummy(), "initSteps", "steps for k-means initialization mode",
                      typeConverter=TypeConverters.toInt)

    @keyword_only
    def __init__(self, featuresCol="features", predictionCol="prediction", k=2,
                 initMode="k-means||", initSteps=5, tol=1e-4, maxIter=20, seed=None):
        """
        __init__(self, featuresCol="features", predictionCol="prediction", k=2, \
                 initMode="k-means||", initSteps=5, tol=1e-4, maxIter=20, seed=None)
        """
        super(KMeans, self).__init__()
        self._java_obj = self._new_java_obj("org.apache.spark.ml.clustering.KMeans", self.uid)
        self._setDefault(k=2, initMode="k-means||", initSteps=5, tol=1e-4, maxIter=20)
        kwargs = self.__init__._input_kwargs
        self.setParams(**kwargs)

    def _create_model(self, java_model):
        return KMeansModel(java_model)

    @keyword_only
    @since("1.5.0")
    def setParams(self, featuresCol="features", predictionCol="prediction", k=2,
                  initMode="k-means||", initSteps=5, tol=1e-4, maxIter=20, seed=None):
        """
        setParams(self, featuresCol="features", predictionCol="prediction", k=2, \
                  initMode="k-means||", initSteps=5, tol=1e-4, maxIter=20, seed=None)

        Sets params for KMeans.
        """
        kwargs = self.setParams._input_kwargs
        return self._set(**kwargs)

    @since("1.5.0")
    def setK(self, value):
        """
        Sets the value of :py:attr:`k`.
        """
        self._set(k=value)
        return self

    @since("1.5.0")
    def getK(self):
        """
        Gets the value of `k`
        """
        return self.getOrDefault(self.k)

    @since("1.5.0")
    def setInitMode(self, value):
        """
        Sets the value of :py:attr:`initMode`.
        """
        self._set(initMode=value)
        return self

    @since("1.5.0")
    def getInitMode(self):
        """
        Gets the value of `initMode`
        """
        return self.getOrDefault(self.initMode)

    @since("1.5.0")
    def setInitSteps(self, value):
        """
        Sets the value of :py:attr:`initSteps`.
        """
        self._set(initSteps=value)
        return self

    @since("1.5.0")
    def getInitSteps(self):
        """
        Gets the value of `initSteps`
        """
        return self.getOrDefault(self.initSteps)


class BisectingKMeansModel(JavaModel, JavaMLWritable, JavaMLReadable):
    """
    .. note:: Experimental

    Model fitted by BisectingKMeans.

    .. versionadded:: 2.0.0
    """

    @since("2.0.0")
    def clusterCenters(self):
        """Get the cluster centers, represented as a list of NumPy arrays."""
        return [c.toArray() for c in self._call_java("clusterCenters")]

    @since("2.0.0")
    def computeCost(self, dataset):
        """
        Computes the sum of squared distances between the input points
        and their corresponding cluster centers.
        """
        return self._call_java("computeCost", dataset)


@inherit_doc
class BisectingKMeans(JavaEstimator, HasFeaturesCol, HasPredictionCol, HasMaxIter, HasSeed,
                      JavaMLWritable, JavaMLReadable):
    """
    .. note:: Experimental

    A bisecting k-means algorithm based on the paper "A comparison of document clustering
    techniques" by Steinbach, Karypis, and Kumar, with modification to fit Spark.
    The algorithm starts from a single cluster that contains all points.
    Iteratively it finds divisible clusters on the bottom level and bisects each of them using
    k-means, until there are `k` leaf clusters in total or no leaf clusters are divisible.
    The bisecting steps of clusters on the same level are grouped together to increase parallelism.
    If bisecting all divisible clusters on the bottom level would result more than `k` leaf
    clusters, larger clusters get higher priority.

    >>> from pyspark.mllib.linalg import Vectors
    >>> data = [(Vectors.dense([0.0, 0.0]),), (Vectors.dense([1.0, 1.0]),),
    ...         (Vectors.dense([9.0, 8.0]),), (Vectors.dense([8.0, 9.0]),)]
    >>> df = sqlContext.createDataFrame(data, ["features"])
    >>> bkm = BisectingKMeans(k=2, minDivisibleClusterSize=1.0)
    >>> model = bkm.fit(df)
    >>> centers = model.clusterCenters()
    >>> len(centers)
    2
    >>> model.computeCost(df)
    2.000...
    >>> transformed = model.transform(df).select("features", "prediction")
    >>> rows = transformed.collect()
    >>> rows[0].prediction == rows[1].prediction
    True
    >>> rows[2].prediction == rows[3].prediction
    True
    >>> bkm_path = temp_path + "/bkm"
    >>> bkm.save(bkm_path)
    >>> bkm2 = BisectingKMeans.load(bkm_path)
    >>> bkm2.getK()
    2
    >>> model_path = temp_path + "/bkm_model"
    >>> model.save(model_path)
    >>> model2 = BisectingKMeansModel.load(model_path)
    >>> model.clusterCenters()[0] == model2.clusterCenters()[0]
    array([ True,  True], dtype=bool)
    >>> model.clusterCenters()[1] == model2.clusterCenters()[1]
    array([ True,  True], dtype=bool)

    .. versionadded:: 2.0.0
    """

    k = Param(Params._dummy(), "k", "number of clusters to create",
              typeConverter=TypeConverters.toInt)
    minDivisibleClusterSize = Param(Params._dummy(), "minDivisibleClusterSize",
                                    "the minimum number of points (if >= 1.0) " +
                                    "or the minimum proportion",
                                    typeConverter=TypeConverters.toFloat)

    @keyword_only
    def __init__(self, featuresCol="features", predictionCol="prediction", maxIter=20,
                 seed=None, k=4, minDivisibleClusterSize=1.0):
        """
        __init__(self, featuresCol="features", predictionCol="prediction", maxIter=20, \
                 seed=None, k=4, minDivisibleClusterSize=1.0)
        """
        super(BisectingKMeans, self).__init__()
        self._java_obj = self._new_java_obj("org.apache.spark.ml.clustering.BisectingKMeans",
                                            self.uid)
        self._setDefault(maxIter=20, k=4, minDivisibleClusterSize=1.0)
        kwargs = self.__init__._input_kwargs
        self.setParams(**kwargs)

    @keyword_only
    @since("2.0.0")
    def setParams(self, featuresCol="features", predictionCol="prediction", maxIter=20,
                  seed=None, k=4, minDivisibleClusterSize=1.0):
        """
        setParams(self, featuresCol="features", predictionCol="prediction", maxIter=20, \
                  seed=None, k=4, minDivisibleClusterSize=1.0)
        Sets params for BisectingKMeans.
        """
        kwargs = self.setParams._input_kwargs
        return self._set(**kwargs)

    @since("2.0.0")
    def setK(self, value):
        """
        Sets the value of :py:attr:`k`.
        """
        self._set(k=value)
        return self

    @since("2.0.0")
    def getK(self):
        """
        Gets the value of `k` or its default value.
        """
        return self.getOrDefault(self.k)

    @since("2.0.0")
    def setMinDivisibleClusterSize(self, value):
        """
        Sets the value of :py:attr:`minDivisibleClusterSize`.
        """
        self._set(minDivisibleClusterSize=value)
        return self

    @since("2.0.0")
    def getMinDivisibleClusterSize(self):
        """
        Gets the value of `minDivisibleClusterSize` or its default value.
        """
        return self.getOrDefault(self.minDivisibleClusterSize)

    def _create_model(self, java_model):
        return BisectingKMeansModel(java_model)


if __name__ == "__main__":
    import doctest
    import pyspark.ml.clustering
    from pyspark.context import SparkContext
    from pyspark.sql import SQLContext
    globs = pyspark.ml.clustering.__dict__.copy()
    # The small batch size here ensures that we see multiple batches,
    # even in these small test examples:
    sc = SparkContext("local[2]", "ml.clustering tests")
    sqlContext = SQLContext(sc)
    globs['sc'] = sc
    globs['sqlContext'] = sqlContext
    import tempfile
    temp_path = tempfile.mkdtemp()
    globs['temp_path'] = temp_path
    try:
        (failure_count, test_count) = doctest.testmod(globs=globs, optionflags=doctest.ELLIPSIS)
        sc.stop()
    finally:
        from shutil import rmtree
        try:
            rmtree(temp_path)
        except OSError:
            pass
    if failure_count:
        exit(-1)
