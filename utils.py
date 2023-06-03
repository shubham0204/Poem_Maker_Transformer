import pickle
import torch


class Predictor:

    def __init__( self , model , idx_to_word , word_to_idx ):
        self.model = model
        self.idx_to_word = idx_to_word
        self.word_to_idx = word_to_idx

    @torch.no_grad()
    def predict_next_word(self, input_seq):
        outputs = self.model( torch.unsqueeze( input_seq , dim=0 ) )
        outputs = outputs[ 0 , -1 , : ]
        max_index = torch.argmax( torch.nn.functional.softmax( outputs , dim=0 ) )
        return self.idx_to_word[ max_index.item() ]

    def predict_tokens( self , input_seq  , num_tokens ):
        preds = []
        input_seq = [ self.word_to_idx[ word ] for word in input_seq ]
        for i in range( num_tokens ):
            input_seq = torch.tensor( input_seq )
            predicted_token = self.predict_next_word( input_seq[ i : ] )
            preds.append( predicted_token )
            input_seq = input_seq.tolist()
            input_seq.append( self.word_to_idx[ predicted_token ] )
        return preds


def save_dict_as_pickle( data : dict , filename : str ):
    with open( filename , "wb" ) as file:
        pickle.dump( data , file )

def load_dict_from_pickle( filename ) -> dict:
    with open( filename , "rb" ) as file:
        return pickle.load( file )

