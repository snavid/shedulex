# ==========================================
# ENGLISH TO ARABIC TRANSLATOR
# ==========================================

# ==========================================
# IMPORT MODULES
# ==========================================

from googletrans import Translator

# ==========================================
# CREATE TRANSLATOR OBJECT
# Module: googletrans
# ==========================================

translator = Translator()

# ==========================================
# READ ENGLISH WORDS FROM FILE
# ==========================================

input_file = "words.txt"

with open(input_file, "r", encoding="utf-8") as file:

    english_words = file.readlines()

# ==========================================
# REMOVE EMPTY SPACES
# ==========================================

english_words = [word.strip() for word in english_words]

# ==========================================
# TRANSLATE WORDS
# ==========================================

translated_results = []

print("\n===== TRANSLATION STARTED =====\n")

for word in english_words:

    try:

        # Translate English -> Arabic
        translation = translator.translate(
            word,
            src='en',
            dest='ar'
        )

        arabic_word = translation.text

        # Store translation
        translated_results.append(
            f"{word}  -->  {arabic_word}"
        )

        # Print result
        print(f"{word}  -->  {arabic_word}")

    except Exception as error:

        print(f"Error translating {word}")

        translated_results.append(
            f"{word} --> ERROR"
        )

# ==========================================
# SAVE TRANSLATIONS TO FILE
# ==========================================

output_file = "translated_words.txt"

with open(output_file, "w", encoding="utf-8") as file:

    for line in translated_results:

        file.write(line + "\n")

# ==========================================
# FINISH MESSAGE
# ==========================================

print("\n===== TRANSLATION COMPLETE =====")

print(f"Saved translations to {output_file}")