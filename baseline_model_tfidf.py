import json
import random
import re # regex
import time
# Ignore  the warnings
import warnings
warnings.filterwarnings('always')
warnings.filterwarnings('ignore')

# data manipulation
import numpy as np
import string

# Preprocessing
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords

# For Vectorizing
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MultiLabelBinarizer
from gensim.models import Word2Vec

# Model Selection
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from sklearn.model_selection import train_test_split

# Classification
from sklearn.svm import LinearSVC
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.pipeline import Pipeline
from skmultilearn.problem_transform import BinaryRelevance, LabelPowerset, ClassifierChain
from sklearn.ensemble import RandomForestClassifier

# Evaluation
import sklearn.metrics as metrics
from sklearn.metrics import multilabel_confusion_matrix
from sklearn.metrics import precision_recall_curve
import matplotlib.pyplot as plt

dataset_file_path = 'top_40_labels_dataset.json'


def create_x_y():

    with open(dataset_file_path) as fp:
        dataset_json = json.load(fp)

    x = [] # policy texts
    y = [] # labels

    random.shuffle(dataset_json)
    for datapoint in dataset_json:
        x.append(datapoint['policy_text'])
        y.append(datapoint['labels'])

    # print(f"Loaded {len(x)} policies with {len(y)} corresponding sets of policy practices")
    return x, y


# create x and y
X, y = create_x_y()


# ----- Preprocessing -----
# function to preprocess the policy text
def preprocess_texts(text):
    text = text.lower()
    text = re.sub(re.compile('<.*?>'), '', text)
    text = text.translate(str.maketrans('', '', string.punctuation))

    word_tokens = text.split()
    le=WordNetLemmatizer()
    stop_words = set(stopwords.words("english"))
    word_tokens = [le.lemmatize(w) for w in word_tokens if not w in stop_words]

    cleaned_text = " ".join(word_tokens)

    return cleaned_text


# map the function to preprocess the data
clean_data = list(map(lambda text: preprocess_texts(text), X))

# Use MultilabelBinarizer to vectorize the labels
mlb = MultiLabelBinarizer()
y_mlb = mlb.fit_transform(y)
# print(mlb.classes_[1000:1500])

# split the data set into training and testing
X_train, X_test, y_train, y_test = train_test_split(clean_data, y_mlb, test_size=0.3, random_state=42)


# ---- Feature Engineering ----
# tfidf-vectorizer the policy text
tfidf = TfidfVectorizer(analyzer='word', max_features=1000)
X_train_tfidf = tfidf.fit_transform(X_train)
X_test_tfidf = tfidf.transform(X_test)

# print(tfidf.vocabulary_)


# shapes of x and y
# print(X_train_tfidf.shape)
# print(X_test_tfidf.shape)
# print(y_train.shape)
# print(y_test.shape)

# ----- Binary Relevance with RandomForestClassifier -----
# each target variable(y1,y2,...) is treated independently and reduced to n classification problems
start=time.time()
base_classifier = BinaryRelevance(
    classifier=RandomForestClassifier(n_estimators=300, min_samples_split=2, min_samples_leaf=1, max_features='auto',
                                      max_depth=16, random_state=42),
    require_dense=[True, True])

# fit the model
base_classifier.fit(X_train_tfidf, y_train)

print('training time taken: ', round(time.time()-start, 0), 'seconds')

# get the predictions
start=time.time()
y_pred = base_classifier.predict(X_test_tfidf)
print('prediction time taken....', round(time.time()-start, 0), 'seconds')

# return the models metrics
br_prec = metrics.precision_score(y_test, y_pred, average='macro')
br_rec = metrics.recall_score(y_test, y_pred, average='macro')
br_f1 = metrics.f1_score(y_test, y_pred, average='weighted')
br_hamm = metrics.hamming_loss(y_test, y_pred)
clf_rep = multilabel_confusion_matrix(y_test, y_pred)

# display score
print('Precision: ', round(br_prec, 3))
print('Recall: ', round(br_rec, 3))
print('F1-score:', round(br_f1, 3))
print('Hamming Loss:', round(br_hamm, 3))

"""
Precision:  0.521
Recall:  0.142
F1-score: 0.266
Hamming Loss: 0.032
"""

# ----- gridsearch ------
# parameters = {
#     'classifier': [BinaryRelevance()],
#     'classifier__classifier': [LinearSVC()],
#     'classifier__classifier__C':[1.0, 5.0, 10.0, 15.0, 20.0],
#     'classifier_classifier__tol': [0.0001, 0.00001, 0.000001, 0.00000001]
# }
#

# clf = GridSearchCV(LinearSVC(), parameters, scoring='f1_macro')

# grid_param = {
#     'classifier__n_estimators': [100, 200, 400, 600],
#     # 'classifier__classifier__min_samples_split': [2, 5, 10],
#     # 'classifier__classifier__min_samples_leaf': [1, 2, 4]
#     # 'classifier__classifier__max_depth': [10, 20, 30, 40, 50, 60]
#     }
#
# clf = GridSearchCV(base_classifier, param_grid=grid_param, scoring='f1_macro')
# clf.fit(X_train_tfidf, y_train)
#
# print(clf.estimator.get_params().keys())
# print(clf.best_params_)















