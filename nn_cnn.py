import json
import random
import re
import string
import time
import os

import gensim.models.phrases
import numpy as np
import pickle
from keras.models import load_model

# Preprocessing
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from sklearn.model_selection import train_test_split
from keras.preprocessing.text import Tokenizer
from keras_preprocessing.sequence import pad_sequences

# For Vectorization
from sklearn.preprocessing import MultiLabelBinarizer
from gensim.models import Word2Vec
from sklearn.utils import compute_class_weight

# building model
import tensorflow as tf
import tensorflow.python.keras.optimizer_v1
from tensorflow import keras
from keras.layers import Dense, Activation, Embedding, GlobalMaxPool1D, Dropout, Conv1D, Conv2D, LSTM, Flatten, BatchNormalization, Bidirectional
from keras.models import Sequential
from keras import Input
from tensorflow.python.keras.optimizer_v1 import Adam
from keras.callbacks import EarlyStopping,ReduceLROnPlateau
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.utils import compute_sample_weight

# metrics
from keras.metrics import Precision, Recall
from keras import backend as K
from sklearn.metrics import average_precision_score
import tensorflow_addons as tfa

# plot
from sklearn.metrics import precision_recall_curve
import matplotlib.pyplot as plt
from matplotlib import pyplot
from sklearn.decomposition import PCA
from keras.utils.vis_utils import plot_model
import graphviz
import pydot



# optuna
import optuna
from optuna import trial

# keras tuner
import keras_tuner
from keras import layers
from keras_tuner import RandomSearch

# load the top labels
dataset_file_path = 'top_40_labels_dataset.json'

with open(dataset_file_path) as fp:
    dataset_json = json.load(fp)


def create_x_y():

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
def preprocess_text(text):
    text = text.lower()
    text = re.sub(re.compile('<.*?>'), '', text)
    text = text.translate(str.maketrans('', '', string.punctuation))
    text = re.sub('\d+', '', text)

    word_tokens = text.split()
    le=WordNetLemmatizer()
    stop_words = set(stopwords.words("english"))
    word_tokens = [le.lemmatize(w) for w in word_tokens if not w in stop_words]

    cleaned_text = " ".join(word_tokens)
    cleaned_text = re.sub(r"\b[a-zA-Z]\b", "", cleaned_text)
    cleaned_text = " ".join(cleaned_text.split())

    return cleaned_text


# map the function to the dataset to preprocess the text
print('--preprocessing data--')
preprocessed_text = list(map(lambda text: preprocess_text(text), X))
print('--preprocessing done--')

# print(f"Original Text: {X[1]}")
# print(" ")
# print(f"Cleaned Text: {preprocessed_text[1]}")


# --------- build the word2vec model ---------
# tokenize the the policy texts (unigrams)
def create_tokens(sentence_list):
    token_data = []
    for sentence in sentence_list:
        tokens = word_tokenize(sentence)
        token_data.append(tokens)
    return token_data


tokenized_data = create_tokens(preprocessed_text)

# tokenized_data = []
# for sentence in preprocessed_text:
#     tokens = word_tokenize(sentence)
#     tokenized_data.append(tokens)


# title = re.sub('\D', '', dataset_file_path)
# word2vec_model_file = 'word2vec_top'+ f'{title}' +'.model'
start = time.time()
w2v_model = Word2Vec(sentences=tokenized_data, size=300, window=7, min_count=1)
print("Time taken to train word2vec model: ", round(time.time()-start, 0), 'seconds')
# w2v_model.save(word2vec_model_file)

w2v_model.train(tokenized_data, epochs=10, total_examples=len(tokenized_data))


def visualize_w2v():
    vector = w2v_model[w2v_model.wv.vocab]
    pca = PCA(n_components=2)
    result = pca.fit_transform(vector)

    plt.scatter(x=result[:, 0], y=result[:, 1])
    words = list(w2v_model.wv.vocab)
    for i, word in enumerate(words):
        plt.annotate(word, size=3, xy=(result[i, 0], result[i, 1]))

    plt.show()


vocab = w2v_model.wv.vocab
print("The total words : ", len(vocab))
vocab = list(vocab.keys()) # list of words in the w2v model


# create a dictionary with word and key as the vectors (used for creating embed matrix)
def create_word_vect_dict(vocab):
    wv_dict = {}
    for word in vocab:
        wv_dict[word] = w2v_model.wv.get_vector(word)
    return wv_dict
    pass


word_vect_dict = create_word_vect_dict(vocab)

# encode the text and define parameters (tokenize the text)
tokenizer = Tokenizer()
tokenizer.fit_on_texts(preprocessed_text)

vocab_size = len(tokenizer.word_index) + 1 # total vocabulary size
encoded_ptext = tokenizer.texts_to_sequences(preprocessed_text) # encoded policy texts with mathematical index
maxlen = 215 # maximum length of each policy text
embed_dim = 300


# creating the embedding matrix
def get_embedding_matrix():
    embed_matrix = np.zeros(shape=(vocab_size, embed_dim))
    hits = 0
    misses = 0

    for word, i in tokenizer.word_index.items():
        embed_vector = word_vect_dict.get(word)
        try:
            if embed_vector is not None:
                embed_matrix[i] = embed_vector
                hits += 1
            else:
                misses += 1
        except:
            pass

    print(f'converted words {hits} ({misses} missed words)')
    return embed_matrix


embedding_matrix = get_embedding_matrix()


# check how many embeddings are nonzeros
def check_coverage(matrix):
    nonzero = np.count_nonzero(np.count_nonzero(matrix, axis=1))
    cal_nonzero = nonzero / vocab_size
    return cal_nonzero


coverage = check_coverage(embedding_matrix)


# find the maximum length = 214
def get_max_len(encoded_text):
    len_all_ptext = []
    for encode in encoded_text:
        len_all_ptext.append(len(encode))
    max_len = max(len_all_ptext)
    return max_len


# pad the sequence of policy text
def pad_text(text):
    padding = pad_sequences(text, maxlen=maxlen, padding='post')
    return padding


padded_text = pad_text(encoded_ptext)


##############################Testing#############################################
def test_token_pad():
    preprocess_text_len = preprocessed_text[3].split()
    print("from: ", preprocessed_text[3], f"| len: {len(preprocess_text_len)}")
    print("from: ", preprocessed_text[5], f"| len: {len(preprocessed_text[5].split())}")

    print("to: ", padded_text[3], f"| len: {len(padded_text[3])}")

    vocab_testing = tokenizer.word_index.get(preprocess_text_len[0])
    print("check: word -->", preprocess_text_len[0], f"in idx --> {vocab_testing} ")
###########################################################################


# split the dataset into training and testing
X_train, X_test, y_train, y_test = train_test_split(padded_text, y, test_size=0.2, random_state=42)

# ------------ binarize the multiple labels ------------
mlb = MultiLabelBinarizer()
y_train_mlb = mlb.fit_transform(y_train)
y_test_mlb = mlb.transform(y_test)
label_classes = mlb.classes_

# create dictionary counters with the key as the label name and the value as the total number of labels
counters = {}
for labels in y:
    for label in labels:
        if counters.get(label) is not None:
            counters[label] += 1
        else:
            counters[label] = 1

# calculates class weights for each label due to label imbalance
class_weights = {}
for index, label in enumerate(label_classes):
    class_weights[index] = len(y) / (counters.get(label))

comp_weight = compute_sample_weight(class_weight='balanced', y=y_train_mlb)


# --- custom metrics ---
def get_f1(y_true, y_pred):
    def get_recall(y_true, y_pred):
        true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
        possible_positives = K.sum(K.round(K.clip(y_true, 0, 1)))
        recall = true_positives / (possible_positives + K.epsilon())
        return recall

    def get_precision(y_true, y_pred):
        true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
        predicted_positives = K.sum(K.round(K.clip(y_pred, 0, 1)))
        precision = true_positives / (predicted_positives + K.epsilon())
        return precision
    precision = get_precision(y_true, y_pred)
    recall = get_recall(y_true, y_pred)
    return 2*((precision*recall)/(precision+recall+K.epsilon()))


############### Build model ################
def build_cnn_model():
    n_classes = len(mlb.classes_)

    model = Sequential()

    model.add(Embedding(vocab_size, embed_dim, input_length=maxlen, weights=[embedding_matrix], trainable=True))
    model.add(Dropout(0.6))

    model.add(Conv1D(220, 3, padding='valid', activation='relu', strides=1))
    model.add(Dropout(0.6))
    model.add(Conv1D(220, 3, padding='valid', activation='relu', strides=1))

    model.add(layers.GlobalMaxPool1D())
    model.add(Flatten())
    model.add(Dense(n_classes, activation='sigmoid'))

    # model.add(Dense(n_classes))
    # model.add(Activation('sigmoid'))

    return model


def hybrid_model():
    n_classes = len(mlb.classes_)

    model = Sequential()

    model.add(Embedding(vocab_size, embed_dim, input_length=maxlen, weights=[embedding_matrix]))
    model.add(Dropout(0.3))

    model.add(Conv1D(64, 3, padding='valid', activation='relu', strides=1))
    model.add(Bidirectional(LSTM(128, dropout=0.4, return_sequences=True)))

    model.add(GlobalMaxPool1D())

    model.add(Dense(220))

    model.add(Dense(n_classes))
    model.add(Activation('sigmoid'))

    return model

def bilstm_model():
    n_classes = len(mlb.classes_)

    model = Sequential()

    model.add(Embedding(vocab_size, embed_dim, input_length=maxlen, weights=[embedding_matrix]))

    model.add(Bidirectional(LSTM(16, dropout=0.7, return_sequences=True)))
    model.add(Bidirectional(LSTM(68, dropout= 0.7, return_sequences=True)))

    model.add(Flatten())

    model.add(Dense(n_classes))
    model.add(Activation('sigmoid'))

    return model


def train_model(epoch=30, batch_size=16, lr=0.001):
    t_model = build_cnn_model()
    t_model.summary()

    opt = keras.optimizers.Adam(learning_rate=lr)
    t_model.compile(loss='binary_crossentropy', optimizer=opt,
                  metrics=[keras.metrics.Precision(), keras.metrics.Recall(), get_f1])

    # fit the model
    history = t_model.fit(X_train, y_train_mlb, epochs=epoch, batch_size=batch_size, validation_split=0.1, shuffle=True)

    end = time.time()
    process = round(end - start, 2)
    print(f'training time taken: {process} seconds')

    # display scores
    score = t_model.evaluate(X_test, y_test_mlb)
    print(f'{t_model.metrics_names[0]}: {score[0]}')
    print(f'{t_model.metrics_names[1]}: {score[1]}')
    print(f'{t_model.metrics_names[2]}: {score[2]}')
    # print(f'{model.metrics_names[3]}: {score[3]}')

    return model

# model = build_cnn_model()
# model = train_model(model) # another way by putting model as parameter
# train_model()

# params
start = time.time()
epoch = 25
# 19-0.01, 17-0.11(high recall),
batch_size = 16
lr = 0.001
opt = keras.optimizers.Adam(learning_rate=lr)

model = hybrid_model()

model.summary()
# plot_model(model, to_file='figures/bilstm_plot.png', show_shapes=True, show_layer_names=True)

# compile the model
model.compile(loss='binary_crossentropy', optimizer=opt, metrics=[keras.metrics.Precision(), keras.metrics.Recall(), get_f1])

# fit the model
history = model.fit(X_train, y_train_mlb, epochs=epoch, batch_size=batch_size, validation_split=0.1, shuffle=True)

end = time.time()
process = round(end - start, 2)
print(f'training time taken: {process} seconds')

# display scores
score = model.evaluate(X_test, y_test_mlb)
print(f'{model.metrics_names[0]}: {score[0]}')
print(f'{model.metrics_names[1]}: {score[1]}')
print(f'{model.metrics_names[2]}: {score[2]}')
print(f'{model.metrics_names[3]}: {score[3]}')

######## Save model and tokenizer ##############
# model.save('cnn_model.h5')
# print('saved model to disk')
#
# with open('tokenizer.pickle', 'wb') as handle:
#     pickle.dump(tokenizer, handle, protocol=pickle.HIGHEST_PROTOCOL)
# print('saved keras tokenizer')

############## plot history ################
# ---- visualize the history ----
def plot_history(history):
    plt.plot(history.history['precision'], label="precision")
    plt.plot(history.history['val_precision'])
    plt.title('Validation Precision History')
    plt.ylabel('Precision value')
    plt.xlabel('No. epoch')
    plt.legend(['train', 'test'], loc='upper left')
    # plt.savefig(f'Precision({lr}-{batch_size}).png')
    plt.show()

    # summarize for loss
    plt.plot(history.history['loss'])
    plt.plot(history.history['val_loss'])
    plt.title('Validation Loss History')
    plt.ylabel('Loss value')
    plt.xlabel('No. epoch')
    plt.legend(['train', 'test'], loc='upper left')
    # plt.savefig(f'Loss({lr}-{batch_size}).png')
    plt.show()

    # summarize for Recall
    plt.plot(history.history['recall'])
    plt.plot(history.history['val_recall'])
    plt.title('Validation Recall History')
    plt.ylabel('Recall value')
    plt.xlabel('No. epoch')
    plt.legend(['train', 'test'], loc='upper left')
    # plt.savefig(f'Recall ({lr}-{batch_size}).png')
    plt.show()

plot_history(history)



exit()
############## Test Model #################
# load the model
loaded_model = load_model('model/cnn_model.h5')

# load tokenizer
with open('model/tokenizer.pickle', 'rb') as handle:
    loaded_tokenizer = pickle.load(handle)

# predict a segment text
txt = X[1]

seq = loaded_tokenizer.texts_to_sequences([txt])

padded = pad_sequences(seq, maxlen=maxlen)

pred = loaded_model.predict(padded)

print(pred)


################## K-fold ####################
def kfold_val():
    cross_val = KFold(n_splits=5, shuffle=True, random_state=42)
    # list of val scores
    val_loss = []
    val_precision = []
    val_recall = []
    fld_score = []

    # params
    lr = 0.01
    opt = keras.optimizers.Adam(learning_rate=lr)
    fold_num = 1

    for train_i, test_i in cross_val.split(X_train, y_train_mlb):
        keras.backend.clear_session()

        # generate print
        print('------------------------------------------')
        print(f'Training for fold {fold_num}....')
        print('------------------------------------------')

        x_train_val, x_test_val = X_train[train_i], X_train[test_i]
        y_train_val, y_test_val = y_train_mlb[train_i], y_train_mlb[test_i]

        model = build_cnn_model()

        rdc_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.1, patience=1, min_lr=1e-06, verbose=1)
        early_stop = EarlyStopping(monitor="val_loss", min_delta=0, patience=10, verbose=1, mode="auto",
                                   baseline=None,
                                   restore_best_weights=True)

        model.compile(loss='binary_crossentropy', metrics=[Precision(), Recall(), get_f1], optimizer='adam')

        histroy = model.fit(x_train_val, y_train_val, validation_data=(x_test_val, y_test_val),
                            epochs=10,
                            callbacks=[rdc_lr, early_stop],
                            verbose=1, batch_size=32)

        print('val_loss: ',min(histroy.history['val_loss']))
        print('val_precision: ', max(histroy.history['val_precision']))
        print('val_recall: ', max(histroy.history['val_recall']))

        val_loss.append(min(histroy.history['val_loss']))
        val_precision.append(max(histroy.history['val_precision']))
        val_recall.append(max(histroy.history['val_recall']))

        y_score = model.predict(X_test)
        fld_score.append(y_score)
        fold_num = fold_num + 1

    return fld_score

# --- get mean score ---
# fold_result = kfold_val()
#
# test_prob = np.mean(fold_result, 0)
# y_true = np.array(y_test_mlb)
#
# print('--- Mean Precision Score --- ')
# mean_avg_precs = average_precision_score(y_true, test_prob, average='weighted')
# print(f'Weighted Mean Precision Score: {mean_avg_precs}')










