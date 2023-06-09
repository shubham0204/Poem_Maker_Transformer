from layers import Transformer
from config import load_global_config
from loss import sparse_crossentropy_with_logits
from tqdm import tqdm
from torch.utils.data import TensorDataset , DataLoader , random_split
from torch import nn
import torch
import wandb
import fire
import os
import datetime

config = load_global_config()
data_config = config.data
train_config = config.train
model_config = config.model
device = torch.device( "cuda" if torch.cuda.is_available() else "cpu" )

if train_config.wandb_logging_enabled:
    wandb.login()

def get_checkpoint_path():
    checkpoints_path = train_config.checkpoint_path
    if train_config.checkpoint_path == "auto":
        checkpoints_path = datetime.datetime.now().strftime("%H_%M_%d_%m_%Y")
    if not os.path.exists(checkpoints_path):
        os.makedirs(checkpoints_path)
    return checkpoints_path

def make_data_loaders( data_tensors_path : str , test_split : float = 0.3 , batch_size : int = 128 ):
    inputs = torch.load( os.path.join( data_tensors_path , "inputs.pt" ) )
    outputs = torch.load( os.path.join( data_tensors_path , "outputs.pt" ) )
    ds = TensorDataset( inputs , outputs )
    train_ds , test_ds = random_split( ds , [ 1 - test_split , test_split ] )
    train_ds_loader = DataLoader( train_ds , batch_size , shuffle=True , drop_last=True )
    test_ds_loader = DataLoader( test_ds , batch_size , shuffle=True , drop_last=True )
    return train_ds_loader , test_ds_loader

def train_epoch( model , train_ds_loader , optimizer ):
    model.train()
    avg_loss = 0.0
    avg_acc = 0.0
    for batch_idx , ( inputs , outputs ) in enumerate( tqdm( train_ds_loader , desc="Training " ) ):
        inputs , outputs = inputs.to( device ) , outputs.to( device )
        optimizer.zero_grad()
        preds = model( inputs )
        preds = preds[ : , -1 , : ]
        loss = sparse_crossentropy_with_logits( preds , outputs )
        loss.backward()
        optimizer.step()
        preds = torch.argmax( torch.nn.functional.softmax( preds , dim=1 ) , dim=1 )
        acc = torch.mean( torch.eq( preds , outputs[ : , -1 ] ).float() )
        avg_loss += loss.cpu().item()
        avg_acc += acc.cpu().item()
    avg_loss /= len( train_ds_loader )
    avg_acc /= len( train_ds_loader )
    return avg_loss , avg_acc

def test_epoch( model , test_ds_loader ):
    model.eval()
    avg_loss = 0.0
    avg_acc = 0.0
    for batch_idx , ( inputs , outputs ) in enumerate( tqdm( test_ds_loader , desc="Testing " ) ):
        inputs, outputs = inputs.to(device), outputs.to(device)
        preds = model( inputs )
        preds = preds[ : , -1 , : ]
        loss = sparse_crossentropy_with_logits( preds , outputs )
        preds = torch.argmax( torch.nn.functional.softmax( preds , dim=1 ) , dim=1 )
        acc = torch.mean( torch.eq( preds , outputs[ : , -1 ] ).float() )
        avg_loss += loss.cpu().item()
        avg_acc += acc.cpu().item()
    avg_loss /= len( test_ds_loader )
    avg_acc /= len( test_ds_loader )
    return avg_loss , avg_acc



train_ds_loader , test_ds_loader = make_data_loaders(
    data_config.data_tensors_path ,
    data_config.test_split ,
    train_config.batch_size
)
ckpt_path = get_checkpoint_path()

model = Transformer(
    vocab_size=data_config.vocab_size ,
    embedding_dim=model_config.embedding_dim ,
    seq_length=data_config.seq_length ,
    num_blocks=model_config.num_blocks ,
    num_heads_in_block=model_config.num_heads_in_block
)
model.to( device )
optimizer = torch.optim.Adam( model.parameters() , lr=0.001 )

if train_config.wandb_logging_enabled:
    wandb.init(
        project=train_config.wandb_project_name ,
        config=model_config.update( train_config )
    )

for e in range( train_config.num_epochs ):
    print( f"--------- EPOCH {e + 1} -----------" )
    train_loss , train_acc = train_epoch( model , train_ds_loader , optimizer )
    val_loss , val_acc = test_epoch( model , test_ds_loader )
    if train_config.wandb_logging_enabled:
        wandb.log( {
                "loss" : train_loss ,
                "acc" : train_acc ,
                "val_loss" : val_loss ,
                "val_acc" : val_acc
            } )
    torch.save(
        model ,
        os.path.join( ckpt_path , "model_{}.pt".format( e + 1 ) )
    )
    print("{} loss={:.5f}, acc={:.5f} , val_loss={:.5f}, val_acc={:.5f}"
          .format(e + 1 , train_loss , train_acc , val_loss , val_acc ) )

