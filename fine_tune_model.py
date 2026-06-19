"""
AgriConnect Ghana: Hugging Face Model Fine-Tuning Pipeline
==========================================================

This script allows you to fine-tune a Hugging Face Vision Transformer (ViT) model 
on a custom plant/crop disease image dataset (e.g., PlantVillage).

Prerequisites:
--------------
To run this script locally or in a GPU-accelerated notebook environment (like Google Colab),
install the following dependencies:
    $ pip install transformers datasets accelerate torchvision evaluate scikit-learn pillow

Usage:
------
1. Run the script:
    $ python fine_tune_model.py
2. Once training is complete, the script saves the fine-tuned model to the `./fine_tuned_disease_model` directory.
3. You can upload it to the Hugging Face Hub:
    $ huggingface-cli login
    $ python -c "from transformers import AutoModel; model = AutoModel.from_pretrained('./fine_tuned_disease_model'); model.push_to_hub('your-username/your-model-name')"
4. Update the endpoint in `ai/views.py` (line 21) to point to your new model URL:
   `api_url = "https://api-inference.huggingface.co/models/your-username/your-model-name"`
"""

import os
import numpy as np
import torch
from datasets import load_dataset
from transformers import (
    AutoImageProcessor, 
    AutoModelForImageClassification, 
    TrainingArguments, 
    Trainer
)
import evaluate

# 1. Configuration Settings
BASE_MODEL = "google/vit-base-patch16-224-in21k"  # Vision Transformer base
DATASET_NAME = "Saon110/bd-crop-vegetable-plant-disease-dataset" # Example plant disease dataset
OUTPUT_DIR = "./fine_tuned_disease_model"

def main():
    print(f"[*] Loading dataset: {DATASET_NAME}...")
    # Load dataset from Hugging Face Hub
    dataset = load_dataset(DATASET_NAME)
    
    # Split training and validation sets if necessary
    if "validation" not in dataset:
        dataset = dataset["train"].train_test_split(test_size=0.15)
        dataset["validation"] = dataset.pop("test")
        
    labels = dataset["train"].features["label"].names
    label2id = {label: str(i) for i, label in enumerate(labels)}
    id2label = {str(i): label for i, label in enumerate(labels)}
    
    print(f"[+] Loaded {len(labels)} classes: {labels}")
    
    # 2. Image Processing & Augmentation
    print(f"[*] Loading image processor: {BASE_MODEL}...")
    image_processor = AutoImageProcessor.from_pretrained(BASE_MODEL)
    
    def transform(example_batch):
        # Process and normalize the batch of images
        inputs = image_processor([x for x in example_batch["image"]], return_tensors="pt")
        inputs["labels"] = example_batch["label"]
        return inputs

    # Apply preprocessing transformations on-the-fly
    prepared_ds = dataset.with_transform(transform)

    # 3. Define Evaluation Metric
    accuracy = evaluate.load("accuracy")
    
    def compute_metrics(eval_pred):
        predictions, labels = eval_pred
        preds = np.argmax(predictions, axis=1)
        return accuracy.compute(predictions=preds, references=labels)

    # 4. Load Pretrained Classification Model
    print(f"[*] Initializing model: {BASE_MODEL}...")
    model = AutoModelForImageClassification.from_pretrained(
        BASE_MODEL,
        num_labels=len(labels),
        id2label=id2label,
        label2id=label2id
    )

    # 5. Define Training Arguments
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        remove_unused_columns=False,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        learning_rate=5e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        num_train_epochs=3,
        weight_decay=0.01,
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        logging_steps=10,
        push_to_hub=False,
    )

    # 6. Initialize Trainer and Start Training
    print("[*] Starting training pipeline...")
    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=collate_fn,
        train_dataset=prepared_ds["train"],
        eval_dataset=prepared_ds["validation"],
        tokenizer=image_processor,
        compute_metrics=compute_metrics,
    )

    train_results = trainer.train()
    
    # Save the fine-tuned model and processor configurations
    print(f"[+] Saving model checkpoints to: {OUTPUT_DIR}")
    trainer.save_model()
    image_processor.save_pretrained(OUTPUT_DIR)
    print("[+] Model fine-tuning completed successfully!")

def collate_fn(batch):
    # custom collator for image tasks
    return {
        "pixel_values": torch.stack([x["pixel_values"] for x in batch]),
        "labels": torch.tensor([x["labels"] for x in batch])
    }

if __name__ == "__main__":
    main()
