from flask import Flask, render_template, request, session, url_for
from googletrans import Translator, LANGUAGES
import asyncio
import os  # For generating a secret key if needed

app = Flask(__name__)

# --- IMPORTANT: Set a SECRET_KEY for session management ---
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_very_strong_and_random_secret_key_for_production')
# In a real app, generate a proper key, e.g., using: import os; print(os.urandom(24).hex())

# Use all languages from googletrans.LANGUAGES
ALL_LANGUAGES_DISPLAY = {
    code: name.capitalize() for code, name in LANGUAGES.items()
}
ALL_LANGUAGES_DISPLAY = dict(sorted(ALL_LANGUAGES_DISPLAY.items(), key=lambda item: item[1]))


def get_language_name(lang_code):
    # Safely get language name, defaulting to the code itself if not found
    if not lang_code:
        return "Unknown"
    return ALL_LANGUAGES_DISPLAY.get(lang_code.lower(), LANGUAGES.get(lang_code.lower(), lang_code).capitalize())


@app.route('/', methods=['GET'])
def index():
    history = session.get('translation_history', [])
    return render_template('index.html',
                           supported_languages=ALL_LANGUAGES_DISPLAY,
                           source_lang='auto',
                           target_lang='es',  # Default target language
                           history=history)


@app.route('/translate', methods=['POST'])
def translate_text():
    text_to_translate = request.form.get('text_to_translate', '').strip()
    source_lang_code = request.form.get('source_lang')
    target_lang_code = request.form.get('target_lang')

    translated_text = ""
    error_message = None
    detected_source_lang_code = None
    detected_source_lang_name = None
    history = session.get('translation_history', [])

    if not text_to_translate:
        error_message = "Please enter text to translate."
    elif not target_lang_code:
        error_message = "Please select a target language."
    elif source_lang_code == target_lang_code and source_lang_code != 'auto':
        error_message = "Source and target languages are the same. No translation performed."
        translated_text = text_to_translate  # Show original text
    else:
        try:
            translator = Translator()
            src_param = source_lang_code if source_lang_code != 'auto' else None

            if src_param:
                translation_object = translator.translate(text_to_translate, src=src_param, dest=target_lang_code)
            else:
                translation_object = translator.translate(text_to_translate, dest=target_lang_code)

            if asyncio.iscoroutine(translation_object):
                actual_translation_result = asyncio.run(translation_object)
            else:
                actual_translation_result = translation_object

            if actual_translation_result:
                translated_text = actual_translation_result.text
                detected_source_lang_code = actual_translation_result.src
                if detected_source_lang_code:
                    detected_source_lang_name = get_language_name(detected_source_lang_code)

                # --- Add to history ---
                if not error_message and translated_text and translated_text.strip() != text_to_translate.strip():  # Only add successful, actual translations
                    final_source_lang_name = get_language_name(
                        detected_source_lang_code) if detected_source_lang_code and source_lang_code == 'auto' else get_language_name(
                        source_lang_code)
                    target_lang_name = get_language_name(target_lang_code)

                    history_entry = {
                        'original': text_to_translate,
                        'translated': translated_text,
                        'source_name': final_source_lang_name,
                        'target_name': target_lang_name,
                        'source_code': detected_source_lang_code if detected_source_lang_code and source_lang_code == 'auto' else source_lang_code,
                        'target_code': target_lang_code
                    }
                    # Avoid duplicates by checking the last entry if it's identical
                    if not history or history[0] != history_entry:
                        history.insert(0, history_entry)
                    session['translation_history'] = history[:10]  # Keep last 10 searches
            else:
                # This case might occur if translation_object is None after asyncio.run
                raise Exception("Translation service returned no result or an unexpected response.")

            # If auto-detect led to same source and target, effectively no translation
            if source_lang_code == 'auto' and detected_source_lang_code == target_lang_code:
                if not translated_text:  # Ensure original text is shown if no translation happened
                    translated_text = text_to_translate
                # Optionally, add a message here if desired, but usually not an error

        except Exception as e:
            app.logger.error(f"Translation error: {e}", exc_info=True)
            error_message = f"An error occurred during translation. The service might be temporarily unavailable or the input might be problematic."
            # You can add more specific error checks based on common googletrans exceptions
            if "invalid destination language" in str(e).lower():
                error_message = "Invalid target language selected. Please ensure it's a supported language."
            elif "AttributeError" in str(e) and "'NoneType' object has no attribute" in str(e):
                error_message = "The translation service returned an empty response. This might be due to API limits or network issues."

    return render_template('index.html',
                           supported_languages=ALL_LANGUAGES_DISPLAY,
                           translated_text=translated_text,
                           original_text=text_to_translate,
                           source_lang=source_lang_code,
                           target_lang=target_lang_code,
                           detected_source_lang=detected_source_lang_code,
                           detected_source_lang_name=detected_source_lang_name,
                           error=error_message,
                           history=history)


@app.route('/clear_history', methods=['POST'])
def clear_history():
    session.pop('translation_history', None)
    history = []
    return render_template('index.html',
                           supported_languages=ALL_LANGUAGES_DISPLAY,
                           source_lang='auto',
                           target_lang='es',
                           history=history,
                           message="Translation history has been cleared.")  # Provide feedback


if __name__ == '__main__':
    app.run(debug=True, port=5001)