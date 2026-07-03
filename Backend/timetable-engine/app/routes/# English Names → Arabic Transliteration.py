# English Names → Arabic Transliteration/Translation
# pip install googletrans==4.0.0-rc1

from googletrans import Translator

translator = Translator()

print("hii")
print(" ENGLISH NAME → ARABIC TRANSLATOR")
print("==============================hii")

while True:
    name = input("\nEnter an English name: ")

    try:
        result = translator.translate(name, src='en', dest='ar')

        print("\n---------------------------")
        print("English Name :", name)
        print("Arabic Output :", result.text)
        print("---------------------------")

    except Exception as e:
        print("Error:", e)

    again = input("\nTranslate another name? (yes/no): ").lower()
    if again != "yes":
        print("Goodbye!")
        break