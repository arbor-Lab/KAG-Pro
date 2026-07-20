This repository contains the code implementation for the paper: "SC-Ques: A Sentence Completion Question Dataset for English as a Second Language Learners".

## Dataset Overview
SC-Ques contains 289,148 sentence completion (SC) questions, categorized as follows:
- C1: 110,645 questions
- C2: 133,249 questions
- C3: 27,886 questions
- C4: 17,368 questions

Note: 84.35% of SC questions have one blank to be filled.


## Installation

### 1. Environment Setup

Create and activate a conda environment:
```bash
conda create --name env python=3.7.5
conda activate env
```

### 2. Install Dependencies

Install PyTorch:
```bash
pip install torch==1.5.0+cu101 torchvision==0.6.0+cu101 -f https://download.pytorch.org/whl/torch_stable.html
```

Install other requirements:
```bash
pip install -r requirements_gpu.txt
```

## Data and Model Preparation

### 1. Dataset

1. Download the SC-Ques dataset from [Dropbox](https://www.dropbox.com/s/lzznin2hxt6rmft/SC-Ques.tar.gz?dl=0)
2. Extract and place the dataset in `./datasets/SC-Ques`

### 2. Pre-trained Models

1. Download the required models from Hugging Face
2. Place the models in `./pretrained_models`

## Usage

### Training

To train the models:
```bash
cd examples
sh train.sh
```

### Prediction

To make predictions on questions:
```bash
cd examples
python predict_question.py bert bert.pkl model_dir
```
