# Contributor: Ebrahim Hany
import os
import tensorflow as tf
from tensorflow.keras import layers, models

IMG_SIZE = 128
BATCH_SIZE = 32
EPOCHS = 30  
BASE_PATH = os.getenv('FIRE_DATASET_PATH', './dataset/Multi-Scale-Fire-Smoke-and-Flame-Dataset') 

def load_and_preprocess(img_path, label):
    img = tf.io.read_file(img_path)
    img = tf.image.decode_jpeg(img, channels=3)
    img = tf.image.resize(img, [IMG_SIZE, IMG_SIZE])
    img = tf.cast(img, tf.float32) / 255.0
    return img, label

def get_dataset(split, augment=False):
    img_dir = os.path.join(BASE_PATH, split, 'images')
    lbl_dir = os.path.join(BASE_PATH, split, 'labels')
    image_paths = []
    labels = []
    for filename in os.listdir(img_dir):
        if filename.endswith(('.jpg', '.png', '.jpeg')):
            lbl_path = os.path.join(lbl_dir, os.path.splitext(filename)[0] + '.txt')
            if os.path.exists(lbl_path) and os.path.getsize(lbl_path) > 0:
                with open(lbl_path, 'r') as f:
                    content = f.read().strip().split()
                    if content:
                        image_paths.append(os.path.join(img_dir, filename))
                        labels.append(int(float(content[0])))
    ds = tf.data.Dataset.from_tensor_slices((image_paths, labels))
    ds = ds.shuffle(buffer_size=len(image_paths)) if split == 'train' else ds
    ds = ds.map(load_and_preprocess, num_parallel_calls=tf.data.AUTOTUNE)
    if augment:
        data_augmentation = tf.keras.Sequential([
            layers.RandomFlip("horizontal_and_vertical"),
            layers.RandomRotation(0.2),
            layers.RandomContrast(0.1),
        ])
        ds = ds.map(lambda x, y: (data_augmentation(x, training=True), y), 
                    num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)
    return ds

train_ds = get_dataset('train', augment=True)
val_ds = get_dataset('val', augment=False)
test_ds = get_dataset('test', augment=False)

def build_advanced_model():
    model = models.Sequential([
        layers.Input(shape=(IMG_SIZE, IMG_SIZE, 3)),
        
        layers.Conv2D(32, (3, 3), padding='same', activation='relu'),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),

        layers.Conv2D(64, (3, 3), padding='same', activation='relu'),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),

        layers.Conv2D(128, (3, 3), padding='same', activation='relu'),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),

        layers.Conv2D(256, (3, 3), padding='same', activation='relu'),
        layers.BatchNormalization(),
        layers.GlobalAveragePooling2D(),

        layers.Dense(128, activation='relu'),
        layers.Dropout(0.5),
        layers.Dense(1, activation='sigmoid')
    ])
    optimizer = tf.keras.optimizers.Adam(learning_rate=0.0005)
    model.compile(optimizer=optimizer,
                  loss='binary_crossentropy',
                  metrics=['accuracy'])
    return model

model = build_advanced_model()
model.summary()

early_stopping = tf.keras.callbacks.EarlyStopping(
    monitor='val_loss', 
    patience=5, 
    restore_best_weights=True
)
print("starting training ")
history = model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=EPOCHS,
    callbacks=[early_stopping]
)
test_loss, test_acc = model.evaluate(test_ds)
print(f"\nFinal Test Accuracy: {test_acc*100:.2f}%")
model.save('fire.h5')
print("Model saved as fire.h5")