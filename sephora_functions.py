# Import beberapa library yang dibutuhkan
import streamlit as st
import numpy as np # Library python yang umum digunakan untuk operasi numerik, terutama operasi array numerik multidimensi
import pandas as pd # Library python yang digunakan untuk manipulasi dan analisis data, terutama dengan struktur data seperti DataFrames.
from matplotlib import pyplot as plt # Library python untuk membuat visualisasi grafis. Modul 'pyplot' -> antarmuka membuat grafik dan plot
import seaborn as sns # Library python untuk membuat plot statistik yang indah dan informatif
from matplotlib.ticker import NullFormatter
import matplotlib as mpl
from sklearn.model_selection import train_test_split
import torch
# import torch.nn as nn
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from transformers import BertTokenizer, BertModel,BertForSequenceClassification
from torch.utils.data import DataLoader, TensorDataset
from transformers import  AdamW, BertConfig
from torch.utils.data import DataLoader, RandomSampler
from transformers import get_linear_schedule_with_warmup
from transformers.tokenization_utils_base import AddedToken
import time
import datetime
import io
import base64
from torch.nn.functional import softmax
from sklearn.metrics import accuracy_score
import random
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from wordcloud import WordCloud
import gdown

@st.cache_data
def load_dataset():
    df_product_info = pd.read_csv("Assets/product_info.csv")
    df_reviews_1 = pd.read_csv("Assets/reviews_0_250.csv",index_col = 0, dtype={'author_id':'str'})
    df_reviews_2 = pd.read_csv("Assets/reviews_250_500.csv",index_col = 0, dtype={'author_id':'str'})
    df_reviews_3 = pd.read_csv("Assets/reviews_500_750.csv",index_col = 0, dtype={'author_id':'str'})
    df_reviews_4 = pd.read_csv("Assets/reviews_750_1000.csv",index_col = 0, dtype={'author_id':'str'})
    df_reviews_5 = pd.read_csv("Assets/reviews_1000_1500.csv",index_col = 0, dtype={'author_id':'str'})
    df_reviews_6 = pd.read_csv("Assets/reviews_1500_end.csv",index_col = 0, dtype={'author_id':'str'})

    # Merge df reviews
    df_reviews = pd.concat([df_reviews_1,df_reviews_2,df_reviews_3,df_reviews_4,df_reviews_5,df_reviews_6],axis=0)

    # Lets check df_product_info which columns that similar with df_reviews
    cols_to_use = df_product_info.columns.difference(df_reviews.columns) # Identifikasi column-column yang terdapat di df_product_info tetapi tidak ada di df_reviews
    cols_to_use = list(cols_to_use) # Mengubah objek index ke dalam bentuk list
    cols_to_use.append('product_id') # Menambahkan column product_id pada cols_to_use

    # Menggabungkan df_reviews dan df_product_info[cols_to_use] berdasarkan kolom 'product_id'
    df = pd.merge(df_reviews, df_product_info[cols_to_use], how='outer', on=['product_id', 'product_id'])

    # Rename the columns
    df.rename(columns={'review_text':'text', 'is_recommended':'label'},  inplace=True)

    # Get value text
    x = df.text.values

    # Get value label
    y = df.label.values

    return df, x, y

@st.cache_data
def hundformatter(x, pos):
    return str(round(x / 1e4, 1))

@st.cache_data
def create_feedback_plot_streamlit(df):
    # Convert 'submission_time' to datetime and extract year
    df['submission_time'] = pd.to_datetime(df['submission_time'])
    df['year'] = df['submission_time'].dt.year

    # Create a Streamlit app
    fig, (ax1) = plt.subplots(nrows=1, ncols=1, figsize=(15, 8))

    total_feedback = df.groupby('year').sum(numeric_only=True)['total_feedback_count'].reset_index()

    sns.pointplot(data=total_feedback, x='year', y='total_feedback_count', color="blue", label="Total all feedback", ax=ax1)

    total_pos_feedback = df.groupby('year').sum(numeric_only=True)['total_pos_feedback_count'].reset_index()
    sns.pointplot(data=total_pos_feedback, x='year', y='total_pos_feedback_count', color="green", label="Total Positive Feedback", ax=ax1)

    total_neg_feedback = df.groupby('year').sum(numeric_only=True)['total_neg_feedback_count'].reset_index()
    sns.pointplot(data=total_neg_feedback, x='year', y='total_neg_feedback_count', color="red", label="Total Negative Feedback", ax=ax1)

    ax1.yaxis.set_major_formatter(hundformatter)
    ax1.set_ylabel("Total feedback in Thousands")
    ax1.set_xlabel("Years")
    ax1.legend()

    # Display the plot in Streamlit
    st.pyplot(fig)

@st.cache_data
def plot_helpfulness_vs_recommendation(df):
    # Create a Streamlit figure
    fig, ax = plt.subplots()
    
    colors = {'negative': 'red', 'positive': 'green'}

    # Convert the dictionary to a Seaborn palette
    custom_palette = sns.color_palette(list(colors.values()))

    # Use the custom palette in sns.barplot
    sns.barplot(data=df, y='helpfulness', x='label', palette=custom_palette, ax=ax)
    
    # Display the plot in Streamlit
    st.pyplot(fig)

@st.cache_data
def preprocessing_data(df):
    missing = []
    unique = []
    types = []
    variables = []
    count = []

    for item in df.columns:
        variables.append(item)
        missing.append(df[item].isnull().sum())
        unique.append(df[item].nunique())
        types.append(df[item].dtypes)
        count.append(len(df[item]))

    output = pd.DataFrame({
        'variable': variables,
        'dtype': types,
        'count': count,
        'unique': unique,
        'missing': missing,
    })

    df_info = output.sort_values("missing", ascending=False).reset_index(drop=True)

    # Specify columns to drop
    cols_to_drop = """variation_desc
    sale_price_usd
    value_price_usd
    child_max_price
    child_min_price
    review_title"""

    # Remove leading space in each column name
    cols_list = [col.strip() for col in cols_to_drop.split("\n")]

    # Drop the specified columns
    df.drop(columns=cols_list, axis=1, inplace=True)

    # Drop rows with missing values
    df.dropna(axis=0, inplace=True)

    return df

@st.cache_data
def perform_sentiment_analysis(text):
    tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased-finetuned-sst-2-english")
    model = AutoModelForSequenceClassification.from_pretrained("distilbert-base-uncased-finetuned-sst-2-english")

    # Encode the text using the tokenizer
    inputs = tokenizer(text, padding=True, truncation=True, return_tensors='pt')  # 'pt' for PyTorch tensors

    # Use torch.no_grad() to disable gradient computation during inference
    with torch.no_grad():
        outputs = model(**inputs)
    
    # Get the logits and predicted label
    logits = outputs.logits
    predicted_label = torch.argmax(logits, dim=1).item()

    # Convert the predicted label to sentiment
    sentiment = 'Positive' if predicted_label == 1 else 'Negative'
    
    return sentiment

@st.cache_data
# Function to calculate the accuracy of our predictions vs labels
def flat_accuracy(preds, labels):
    pred_flat = np.argmax(preds, axis=1).flatten()
    labels_flat = labels.flatten()
    return np.sum(pred_flat == labels_flat) / len(labels_flat)

@st.cache_data
def generate_wordcloud(text, sentiment_label):
    if sentiment_label == 1:
        # Positive Review
        color_map = "Greens"
    elif sentiment_label == 0:
        # Negative Review
        color_map = "Reds"
    else:
        st.error("Invalid sentiment label. Use 0 for negative or 1 for positive.")
        return None

    # Convert each item to a string, handling potential float values
    text = [str(item) for item in text]

    wordcloud = WordCloud(
        max_words=50,          # Adjust as needed
        max_font_size=80,       # Adjust as needed
        margin=0,
        background_color="white",
        colormap=color_map
    ).generate(' '.join(text))

    fig, ax = plt.subplots()
    plt.figure(figsize=(25, 25))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")
    plt.margins(x=0, y=0)

    img_bytes = io.BytesIO()
    plt.savefig(img_bytes, format='png')
    img_bytes.seek(0)

    # Encode the bytes as base64 to make it serializable
    img_str = base64.b64encode(img_bytes.read()).decode('utf-8')

    # Close the Matplotlib figure to free up resources
    plt.close()

    return img_str