from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
import bcrypt
import re
from transformers import pipeline
import random
import nltk
nltk.download('punkt')

summarizer = pipeline("summarization", model="Falconsai/text_summarization")
question_generator = pipeline("text2text-generation", model="iarfmoose/t5-base-question-generator")
title_generator = pipeline("text2text-generation", model="czearing/article-title-generator")
spelling_correction = pipeline("text2text-generation", model="oliverguhr/spelling-correction-english-base")
keyword = pipeline("text2text-generation", model="beogradjanka/bart_finetuned_keyphrase_extraction")
paraphrase = pipeline("text2text-generation", model="humarin/chatgpt_paraphraser_on_T5_base")
grammar= pipeline("text2text-generation", model="vennify/t5-base-grammar-correction")
engToTr = pipeline("translation", model="Helsinki-NLP/opus-tatoeba-en-tr")
trToEng = pipeline("translation", model="Helsinki-NLP/opus-mt-tc-big-tr-en")


app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

client = MongoClient('mongodb://localhost:27017/')
db = client['mydatabase']
users_collection = db['users']

def split_paragraph_to_sentences(paragraph):
    # Paragrafı cümlelere bölen işlev
    sentences = nltk.sent_tokenize(paragraph)
    return sentences

def join_sentences_to_paragraph(sentences):
    # Cümleleri paragrafa birleştiren işlev
    paragraph = ' '.join(sentences)
    return paragraph

def join_sentences_to_paragraph_translate(sentences):
    # Cümleleri paragrafa birleştiren işlev
    corrected_sentences = [sentence[0]['translation_text'] for sentence in sentences]
    paragraph = ' '.join(corrected_sentences)
    return paragraph

corrected_sentences = []

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('profile'))
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password'].encode('utf-8')

    existing_user = users_collection.find_one({'username': username})
    if existing_user:
        return jsonify({'error': 'Kullanıcı zaten mevcut!'})

    hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
    users_collection.insert_one({'username': username, 'password': hashed_password})
    
    session['username'] = username
    return redirect(url_for('profile'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password'].encode('utf-8')

    user = users_collection.find_one({'username': username})
    if user and bcrypt.checkpw(password, user['password']):
        session['username'] = username
        return redirect(url_for('profile'))
    else:
        return jsonify({'error': 'Geçersiz kullanıcı adı veya şifre!'})

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/get_text/<text_name>')
def get_text(text_name):
    if 'username' not in session:
        return redirect(url_for('index'))
    
    username = session['username']
    
    # Kullanıcı ile ilişkilendirilmiş metni veritabanından al
    user = users_collection.find_one({'username': username})
    texts = user.get('texts', [])
    for text in texts:
        if text['name'] == text_name:
            return text['content']
    
    return 'Metin bulunamadı'

@app.route('/delete_text', methods=['POST'])
def delete_text():
    if 'username' not in session:
        return redirect(url_for('index'))

    username = session['username']
    text_name = request.form['text_name']

    # Kullanıcının metni veritabanından silinmesi
    users_collection.update_one({'username': username}, {'$pull': {'texts': {'name': text_name}}})

    return redirect(url_for('profile'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('index'))
    
    username = session['username']
    global main_text
    global result
    selected_text=""
    if request.method == 'POST':
     print("kaydoldum")
     selected_text = request.form['gosterilenMetin']
     main_text=request.form['metinAlani']
     if request.form['action'] == 'kayit':
        print("kayit alanına girdim")
        user_text = request.form['metinAlani']
        user_text = re.sub(r">\s+<", '><', user_text)
        user_text = user_text.strip()
        text_name = request.form['text_name']

        existing_text = users_collection.find_one({'username': username, 'texts.name': text_name})
        if existing_text:
        # Eğer varsa, mevcut metni güncelleyelim
         users_collection.update_one({'username': username, 'texts.name': text_name}, {'$set': {'texts.$.content': user_text}})
        else:
        # Eğer yoksa, yeni metni ekleyelim
         users_collection.update_one({'username': username}, {'$push': {'texts': {'name': text_name, 'content': user_text}}})
    
        return redirect(url_for('profile'))
     elif request.form['action'] == 'first_action':
         user = users_collection.find_one({'username': username})
         texts = user.get('texts', [])
         text_name = request.form['text_name']
         header="Your summary is here!"
         result=summarizer(selected_text, max_length=1000, min_length=30, do_sample=False)[0]['summary_text']
        #  result=selected_text + " İlk işlem"
         print("ben tıklandım")
         return render_template('rightclick.html', selected_text=selected_text,main_text=main_text ,result=result, header=header,username=username, texts=texts,text_name=text_name)
     elif request.form['action'] == 'second_action':
         user = users_collection.find_one({'username': username})
         texts = user.get('texts', [])
         text_name = request.form['text_name']
         header="A question for you!"
         random_number = random.randint(1, 3)         
         generated_questions = question_generator(selected_text, max_length=50, num_return_sequences=5, num_beams=5, early_stopping=True)
         question=generated_questions[random_number]['generated_text']
         result=question
        #  result=selected_text + " İkinci işlem"
         return render_template('rightclick.html', selected_text=selected_text,main_text=main_text ,result=result, header=header,username=username, texts=texts,text_name=text_name)
     elif request.form['action'] == 'third_action':
         user = users_collection.find_one({'username': username})
         texts = user.get('texts', [])
         header="A title for you!"
         text_name = request.form['text_name']
         random_number = random.randint(1, 3)         
         generated_title = title_generator(selected_text, max_length=50, num_return_sequences=5, num_beams=5, early_stopping=True)
         title=generated_title[random_number]['generated_text']
         result=title
        #  result=selected_text + " 3 işlem"
         return render_template('rightclick.html', selected_text=selected_text,main_text=main_text ,result=result, header=header,username=username, texts=texts,text_name=text_name)
     elif request.form['action'] == 'fourth_action':
         user = users_collection.find_one({'username': username})
         texts = user.get('texts', [])
         text_name = request.form['text_name']
         header="Spelling Correction"
         sentences = split_paragraph_to_sentences(selected_text) 
         for sentence in sentences:
          corrected_sentence = spelling_correction(sentence,max_new_tokens=50)[0]['generated_text'] # Her bir cümleyi işleyip düzeltme işlemi
          corrected_sentences.append(corrected_sentence)
         corrected_paragraph = join_sentences_to_paragraph(corrected_sentences)
         result=corrected_paragraph
         corrected_sentences.clear()
        #  result=selected_text + " 4 işlem"
         return render_template('rightclick.html', selected_text=selected_text,main_text=main_text ,result=result, header=header,username=username, texts=texts,text_name=text_name)
     elif request.form['action'] == 'fifth_action':
         user = users_collection.find_one({'username': username})
         texts = user.get('texts', [])
         text_name = request.form['text_name']
         header="Key Word"         
         result = keyword(selected_text)[0]['generated_text']
        #  result=selected_text + " 5 işlem"
         return render_template('rightclick.html', selected_text=selected_text,main_text=main_text ,result=result, header=header,username=username, texts=texts,text_name=text_name)
     elif request.form['action'] == 'sixth_action':
         user = users_collection.find_one({'username': username})
         texts = user.get('texts', [])
         text_name = request.form['text_name']
         header="Paraphrase"
         sentences = split_paragraph_to_sentences(selected_text)   
         for sentence in sentences:
          corrected_sentence = paraphrase(sentence,max_new_tokens=100)[0]['generated_text'] # Her bir cümleyi işleyip düzeltme işlemi
          corrected_sentences.append(corrected_sentence)
         corrected_paragraph = join_sentences_to_paragraph(corrected_sentences)
         result=corrected_paragraph
         corrected_sentences.clear()         
        #  result=selected_text + " 6 işlem"
         return render_template('rightclick.html', selected_text=selected_text,main_text=main_text ,result=result, header=header,username=username, texts=texts,text_name=text_name)
     elif request.form['action'] == 'seventh_action':
         user = users_collection.find_one({'username': username})
         texts = user.get('texts', [])
         text_name = request.form['text_name']
         header="Grammar Correction"
         sentences = split_paragraph_to_sentences(selected_text)   
         for sentence in sentences:
          corrected_sentence = grammar(sentence,max_new_tokens=50)[0]['generated_text'] # Her bir cümleyi işleyip düzeltme işlemi
          corrected_sentences.append(corrected_sentence)
         corrected_paragraph = join_sentences_to_paragraph(corrected_sentences)
         result=corrected_paragraph
         corrected_sentences.clear()         
        #  result = grammar(selected_text)[0]['generated_text']
        #  result=selected_text + " 7 işlem"
         return render_template('rightclick.html', selected_text=selected_text,main_text=main_text ,result=result, header=header,username=username, texts=texts,text_name=text_name)
     elif request.form['action'] == 'eighth_action':
         user = users_collection.find_one({'username': username})
         texts = user.get('texts', [])
         text_name = request.form['text_name']
         header="English to Turkish Translate"
         sentences = split_paragraph_to_sentences(selected_text)   
         for sentence in sentences:
          corrected_sentence = engToTr(sentence,max_new_tokens=50) # Her bir cümleyi işleyip düzeltme işlemi
          corrected_sentences.append(corrected_sentence)
         corrected_paragraph = join_sentences_to_paragraph_translate(corrected_sentences)
         result=corrected_paragraph
         corrected_sentences.clear()         
        #  result=selected_text + " 8 işlem"
         return render_template('rightclick.html', selected_text=selected_text,main_text=main_text ,result=result, header=header,username=username, texts=texts,text_name=text_name)
     elif request.form['action'] == 'ninth_action':
         user = users_collection.find_one({'username': username})
         texts = user.get('texts', [])
         text_name = request.form['text_name']
         header="Turkish to English Translate"
         sentences = split_paragraph_to_sentences(selected_text)   
         for sentence in sentences:
          corrected_sentence = trToEng(sentence,max_new_tokens=50) # Her bir cümleyi işleyip düzeltme işlemi
          corrected_sentences.append(corrected_sentence)
         corrected_paragraph = join_sentences_to_paragraph_translate(corrected_sentences)
         result=corrected_paragraph
         corrected_sentences.clear()         
        #  result=selected_text + " 9 işlem"
         return render_template('rightclick.html', selected_text=selected_text,main_text=main_text ,result=result, header=header,username=username, texts=texts,text_name=text_name)
     
    # Kullanıcı ile ilişkilendirilmiş metinleri veritabanından al
    user = users_collection.find_one({'username': username})
    texts = user.get('texts', [])
    
    return render_template('rightclick.html', username=username, texts=texts)



if __name__ == '__main__':
    app.run(debug=True)
