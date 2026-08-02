import os
import numpy as np
import joblib
from sklearn.model_selection import LeaveOneOut
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score
import keras
from keras.utils import to_categorical

X_path       = r"D:\ISL PROJECT\words_X.npy"
y_path       = r"D:\ISL PROJECT\words_y.npy"
encoder_path = r"D:\ISL PROJECT\words_label_encoder.pkl"
model_path   = r"D:\ISL PROJECT\words_lstm_model.keras"

def main():
    print("Loading data...")
    X = np.load(X_path)
    y = np.load(y_path)
    
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    # 1. EVALUATION PHASE — Leave-One-Out Cross Validation
    loo = LeaveOneOut()
    all_true = []
    all_pred = []

    print("Running Leave-One-Out Cross Validation...")
    for fold, (train_idx, test_idx) in enumerate(loo.split(X)):
        X_train_fold = X[train_idx]
        X_test_fold  = X[test_idx]
        y_train_fold = y_encoded[train_idx]
        y_test_fold  = y_encoded[test_idx]
        
        # Augment training fold (5 copies, same noise as before)
        X_aug, y_aug = [], []
        for i in range(len(X_train_fold)):
            seq = X_train_fold[i]
            X_aug.append(seq)
            y_aug.append(y_train_fold[i])
            for _ in range(5):
                noisy = np.copy(seq)
                noisy[:, :63]    += np.random.normal(0, 0.02, (30, 63))
                noisy[:, 63:82]  += np.random.normal(0, 3.0,  (30, 19))
                noisy[:, 82:145] += np.random.normal(0, 0.02, (30, 63))
                noisy[:, 145:]   += np.random.normal(0, 3.0,  (30, 19))
                X_aug.append(noisy)
                y_aug.append(y_train_fold[i])
        
        X_aug = np.array(X_aug)
        y_aug = np.array(y_aug)
        y_aug_cat = to_categorical(y_aug, num_classes=len(le.classes_))
        
        # Build and train model for this fold
        inputs  = keras.Input(shape=(30, 164))
        x       = keras.layers.LSTM(128, return_sequences=True)(inputs)
        x       = keras.layers.BatchNormalization()(x)
        x       = keras.layers.Dropout(0.3)(x)
        x       = keras.layers.LSTM(64)(x)
        x       = keras.layers.BatchNormalization()(x)
        x       = keras.layers.Dropout(0.3)(x)
        x       = keras.layers.Dense(64, activation='relu')(x)
        x       = keras.layers.Dropout(0.2)(x)
        outputs = keras.layers.Dense(len(le.classes_), activation='softmax')(x)
        fold_model = keras.Model(inputs, outputs)
        fold_model.compile(optimizer='adam',
                           loss='categorical_crossentropy',
                           metrics=['accuracy'])
        
        fold_model.fit(
            X_aug, y_aug_cat,
            epochs=50,
            batch_size=16,
            verbose=0
        )
        
        pred = fold_model.predict(X_test_fold, verbose=0)
        all_true.append(y_test_fold[0])
        all_pred.append(np.argmax(pred[0]))
        
        word_true = le.inverse_transform([y_test_fold[0]])[0]
        word_pred = le.inverse_transform([np.argmax(pred[0])])[0]
        print(f"Fold {fold+1:2d}: True={word_true:10s} Pred={word_pred:10s} {'✓' if word_true==word_pred else '✗'}")

    print(f"\nLOO Accuracy: {accuracy_score(all_true, all_pred)*100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(
        all_true, all_pred,
        target_names=le.classes_
    ))

    # 2. FINAL MODEL PHASE — Train on ALL data and save
    print("\nTraining final model on all data...")

    # Augment all data (15 copies)
    X_final, y_final = [], []
    for i in range(len(X)):
        X_final.append(X[i])
        y_final.append(y_encoded[i])
        for _ in range(15):
            noisy = np.copy(X[i])
            noisy[:, :63]    += np.random.normal(0, 0.02, (30, 63))
            noisy[:, 63:82]  += np.random.normal(0, 3.0,  (30, 19))
            noisy[:, 82:145] += np.random.normal(0, 0.02, (30, 63))
            noisy[:, 145:]   += np.random.normal(0, 3.0,  (30, 19))
            X_final.append(noisy)
            y_final.append(y_encoded[i])

    X_final = np.array(X_final)
    y_final = np.array(y_final)
    y_final_cat = to_categorical(y_final, num_classes=len(le.classes_))

    # Build final model
    inputs  = keras.Input(shape=(30, 164))
    x       = keras.layers.LSTM(128, return_sequences=True)(inputs)
    x       = keras.layers.BatchNormalization()(x)
    x       = keras.layers.Dropout(0.3)(x)
    x       = keras.layers.LSTM(64)(x)
    x       = keras.layers.BatchNormalization()(x)
    x       = keras.layers.Dropout(0.3)(x)
    x       = keras.layers.Dense(64, activation='relu')(x)
    x       = keras.layers.Dropout(0.2)(x)
    outputs = keras.layers.Dense(len(le.classes_), activation='softmax')(x)
    final_model = keras.Model(inputs, outputs)
    final_model.compile(optimizer='adam',
                        loss='categorical_crossentropy',
                        metrics=['accuracy'])

    callbacks = [
        keras.callbacks.EarlyStopping(
            patience=20,
            restore_best_weights=True,
            monitor='loss'
        )
    ]

    final_model.fit(
        X_final, y_final_cat,
        epochs=150,
        batch_size=16,
        callbacks=callbacks,
        verbose=1
    )

    final_model.save(model_path)
    joblib.dump(le, encoder_path)
    print(f"Model saved to {model_path}")
    print("Done!")

if __name__ == "__main__":
    main()
