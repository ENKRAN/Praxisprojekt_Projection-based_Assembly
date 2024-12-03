import os
import json
from datetime import datetime

class ManualCreater:
    def __init__(self, tag_id, base_image_dir="data/saved_images", base_instruction_dir="data/saved_images/drawings"):
        self.tag_id = tag_id
        self.steps = []
        self.base_image_dir = base_image_dir
        self.base_instruction_dir = base_instruction_dir
        os.makedirs(self.base_image_dir, exist_ok=True)
        os.makedirs(self.base_instruction_dir, exist_ok=True)

    def capture_photo(self, step_number):
        # Schritt 1: Foto aufnehmen
        photo_path = os.path.join(self.base_image_dir, f"instruction_{self.tag_id}_step{step_number}.png")
        print(f"Simuliere Fotoaufnahme und speichere als: {photo_path}")
        # Hier könnte deine Fotoaufnahme-Logik integriert werden
        return photo_path

    def create_step(self, step_number):
        # Schritte 1–4 für einen Schritt der Anleitung
        photo_path = self.capture_photo(step_number)
        self.open_in_paint(photo_path)
        transformed_data = self.extract_non_black_pixels(photo_path)
        valid = self.project_and_validate(transformed_data)

        if valid:
            # Schritt speichern
            self.steps.append({
                "step": step_number,
                "image_path": photo_path,
                "transformed_data": transformed_data
            })
            print(f"Schritt {step_number} erfolgreich erstellt.")
        else:
            print(f"Schritt {step_number} wurde nicht validiert. Wiederhole den Schritt.")

    def save_instruction(self):
        # Schritt 5: Speichere die gesamte Anleitung
        instruction_data = {
            "tag_id": self.tag_id,
            "steps": self.steps,
            "created_at": datetime.now().isoformat()
        }
        json_path = os.path.join(self.base_instruction_dir, f"instruction_{self.tag_id}.json")
        with open(json_path, "w") as file:
            json.dump(instruction_data, file, indent=4)
        print(f"Anleitung für Tag-ID {self.tag_id} gespeichert: {json_path}")

    def create_instruction(self):
        print(f"Beginne mit der Erstellung der Anleitung für Tag-ID {self.tag_id}.")
        step_number = 1
        while True:
            print(f"Erstelle Schritt {step_number}.")
            self.create_step(step_number)

            # Fragt den Benutzer, ob er weitere Schritte hinzufügen möchte
            add_more = input("Möchtest du einen weiteren Schritt hinzufügen? (y/n): ").lower()
            if add_more != "y":
                break
            step_number += 1

        self.save_instruction()
        print("Anleitung abgeschlossen.")
