import time

class WordBuilder:
    def __init__(self, confidence_threshold=0.30, stability_duration=1.0):
        self.confidence_threshold = confidence_threshold
        self.stability_duration = stability_duration
        
        self.current_word = ""
        self.full_sentence = ""
        
        self.tracking_letter = None
        self.tracking_start_time = 0
        
        self.last_committed_letter = None
        self.last_hand_time = time.time()
        self.last_gap_duration = 0.0
        
        self.hand_was_visible = False
        self.space_added = True
        
        self.mismatch_count = 0
        self.pending_letter = None

    def process_frame(self, letter, confidence, hand_detected=True):
        current_time = time.time()
        
        if not hand_detected or confidence < self.confidence_threshold:
            if self.hand_was_visible:
                self.hand_was_visible = False
                self.tracking_letter = None # Reset tracking when hand drops
                
            gap_duration = current_time - self.last_hand_time
            
            # Gap > 2.0s -> insert space
            if gap_duration > 2.0 and not self.space_added:
                if self.current_word:
                    self.full_sentence += self.current_word + " "
                    self.current_word = ""
                else:
                    if not self.full_sentence.endswith(" "):
                        self.full_sentence += " "
                self.space_added = True
                self.last_committed_letter = None
            return
            
        # Hand is detected with high confidence
        if not self.hand_was_visible:
            # Hand just reappeared, record how long it was gone
            self.last_gap_duration = current_time - self.last_hand_time
            self.hand_was_visible = True
            self.space_added = False
            
        self.last_hand_time = current_time
        
        # Debouncing and tracking with tolerance
        if letter != self.tracking_letter:
            if letter == self.pending_letter:
                self.mismatch_count += 1
            else:
                self.mismatch_count = 1
                self.pending_letter = letter

            if self.mismatch_count >= 3:
                self.tracking_letter = letter
                self.tracking_start_time = current_time
                self.mismatch_count = 0
        else:
            self.mismatch_count = 0
            
            tracking_duration = current_time - self.tracking_start_time
            
            # Check if letter has been stable for ~1 second
            if tracking_duration >= self.stability_duration:
                if letter != self.last_committed_letter:
                    # New letter, commit it
                    self._commit_letter(letter)
                    self.tracking_start_time = current_time # Reset to avoid rapid-fire
                else:
                    # Same letter as last committed. Check gap duration.
                    if self.last_gap_duration >= 0.3:
                        # Gap 0.3s+ -> potential double letter or new letter
                        self._commit_letter(letter)
                        self.tracking_start_time = current_time
                        self.last_gap_duration = 0.0 # Consume gap
                    else:
                        # Gap < 0.3s -> ignore, still signing the same letter
                        self.tracking_start_time = current_time

    def _commit_letter(self, letter):
        self.current_word += letter
        self.last_committed_letter = letter
        
    def delete_last(self):
        if len(self.current_word) > 0:
            self.current_word = self.current_word[:-1]
            self.last_committed_letter = self.current_word[-1] if self.current_word else None
            self.last_gap_duration = 0.0
        elif len(self.full_sentence) > 0:
            self.full_sentence = self.full_sentence[:-1]
            
    def get_state(self):
        return {
            "word": self.current_word,
            "sentence": self.full_sentence,
            "display_text": self.full_sentence + self.current_word
        }
