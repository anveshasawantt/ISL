import os, sys, numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Input, LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.utils import to_categorical
from utils import normalize_seq

CATEGORY = sys.argv[1] if len(sys.argv) > 1 else "GREETINGS"
KP_DIR = os.path.join("keypoints_hands", CATEGORY)
signs = sorted(os.listdir(KP_DIR))
print("Signs:", signs)

X, y = [], []
for i, sign in enumerate(signs):
    for f in os.listdir(os.path.join(KP_DIR, sign)):
        X.append(normalize_seq(np.load(os.path.join(KP_DIR, sign, f))))
        y.append(i)
X, y = np.array(X), np.array(y)
print("Samples:", X.shape)      # expect (N, 30, 90)

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

def augment(X, y, copies=15):
    rng = np.random.default_rng(0)
    Xa, ya = [X], [y]
    for _ in range(copies):
        scale = rng.uniform(0.95, 1.05, size=(len(X), 1, 1))
        noise = rng.normal(0, 0.02, size=X.shape)
        Xa.append(X * scale + noise)
        ya.append(y)
    return np.concatenate(Xa), np.concatenate(ya)

X_tr, y_tr = augment(X_tr, y_tr)
y_tr_c = to_categorical(y_tr, len(signs))
y_te_c = to_categorical(y_te, len(signs))

model = Sequential([
    Input(shape=(30, X.shape[2])),
    LSTM(64, return_sequences=True, activation="tanh"),
    Dropout(0.3),
    LSTM(128, return_sequences=False, activation="tanh"),
    Dense(64, activation="relu"),
    Dropout(0.4),
    Dense(len(signs), activation="softmax"),
])
model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
model.fit(X_tr, y_tr_c, epochs=150, batch_size=16, validation_data=(X_te, y_te_c),
          callbacks=[EarlyStopping(monitor="val_loss", patience=20, restore_best_weights=True)])

os.makedirs("models", exist_ok=True)
model.save(os.path.join("models", f"{CATEGORY}_hands.h5"))
np.save(os.path.join("models", f"{CATEGORY}_hands_labels.npy"), np.array(signs))

print("Test accuracy:", model.evaluate(X_te, y_te_c, verbose=0)[1])
pred = model.predict(X_te).argmax(1)
print(classification_report(y_te, pred, labels=list(range(len(signs))), target_names=signs, zero_division=0))