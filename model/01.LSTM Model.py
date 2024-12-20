import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler,RobustScaler
import holidays
from datetime import timedelta


model_data = df2.copy()

model_data['사골_dif'] = model_data['사골'].diff()
model_data['잡뼈_dif'] = model_data['잡뼈'].diff()
model_data.dropna(inplace=True)
model_data.drop(columns = ['사골','잡뼈'], inplace=True)

# 하이퍼파라미터
torch.manual_seed(0)  ## seed 고정
seq_length = 90        ## 지난 90일 데이터를 통해 예측
input_size = 19        ## input 사이즈 (변수 수)
hidden_size = 64     ## hidden state 사이즈
output_size = 30      ## output 사이즈 (미래 30일 예측)
learning_rate = 0.01  ## lr
epochs = 103       ## 학습 수
batch_size = 32     ## 배치 사이즈
drop_out = 0.4

# 데이터셋 생성 함수
def build_dataset(data, input_seq_len, output_size):
    X, Y = [], []
    for i in range(len(data) - input_seq_len - output_size + 1):
        x = data[i:i+input_seq_len, :-1]  # 입력 시퀀스
        y = data[i+input_seq_len:i+input_seq_len+output_size, -1]  # 출력 시퀀스
        X.append(x)
        Y.append(y)
    return np.array(X), np.array(Y)



train_Set = model_data[model_data['주문일자'] < '2024-01-01']
test_Set = model_data[model_data['주문일자'] >= '2024-01-01']

train_Set.drop(columns='주문일자', inplace=True)
test_Set.drop(columns='주문일자', inplace=True)

scaler_x = MinMaxScaler()
scaler_y = MinMaxScaler()

train_Set_x = scaler_x.fit_transform(train_Set)  # x 정규화
train_Set_y = scaler_y.fit_transform(train_Set[['총합계']].values)  # y 정규화
test_Set_x = scaler_x.transform(test_Set)  # x 정규화
test_Set_y = scaler_y.transform(test_Set[['총합계']].values)  #y 정규화

x_train, y_train = build_dataset(np.hstack((train_Set_x, train_Set_y)), seq_length,output_size)
x_test, y_test = build_dataset(np.hstack((test_Set_x, test_Set_y)), seq_length,output_size)


x_train_tensor = torch.FloatTensor(x_train)
y_train_tensor = torch.FloatTensor(y_train)
x_test_tensor = torch.FloatTensor(x_test)
y_test_tensor = torch.FloatTensor(y_test)


train_dataset = TensorDataset(x_train_tensor, y_train_tensor)

## 텐서 데이터 생성
dataloader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=True)



# LSTM 모델 정의
class LSTM(nn.Module):
    def __init__(self, input_size, hidden_size, seq_length, output_size, drop_out,layers):
        super(LSTM, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.seq_length = seq_length
        self.output_size = output_size
        self.drop_out = drop_out
        self.layers = layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers=layers, batch_first=True, dropout=drop_out)
        self.fc = nn.Linear(hidden_size, output_size,bias=True)
    def forward(self, x):

        x, _hidden_state = self.lstm(x)
        x = self.fc(x[:, -1, :])  # 마지막 타임스텝만 사용
        return x




def train_model(model, data, x_test_tensor, y_test_tensor, scaler_y, epochs=None, lr=learning_rate, verbose=2):
    criterion = nn. SmoothL1Loss()
    optimizer = optim.NAdam(model.parameters(), lr=lr)
    train_hist = np.zeros(epochs)

    for epoch in range(epochs):
        model.train()
        avg_cost = 0
        total_batch = len(data)

        for batch_idx, samples in enumerate(data):
            x_tt, y_tt = samples
            x_tt, y_tt = x_tt.to(torch.float32), y_tt.to(torch.float32)

            outputs = model(x_tt)
            loss = criterion(outputs, y_tt)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            avg_cost += loss.item() / total_batch

        train_hist[epoch] = avg_cost

        if verbose > 0:
          print(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_cost:.4f}")

    return model, train_hist



# 모델 생성 및 학습
lstm_model = LSTM(input_size, hidden_size, seq_length, output_size, layers=4, drop_out = drop_out)
model,train_hist = train_model(
    lstm_model, dataloader, x_test_tensor, y_test_tensor, scaler_y, epochs=epochs, lr=learning_rate, verbose=2
)

# Evaluation on test data
model.eval()  # 평가 모드로 전환
with torch.no_grad():
    pred = []
    for pr in range(len(x_test_tensor)):
        sample = torch.unsqueeze(x_test_tensor[pr], 0)  # [1, seq_length, input_size]
        predicted = model(sample)
        predicted = predicted.flatten().tolist(
        pred.append(predicted)

    # 예측 값과 실제 값 역변환
    pred_inverse = scaler_y.inverse_transform(np.array(pred).reshape(-1, y_test_tensor.shape[1]))
    y_test_inverse = scaler_y.inverse_transform(y_test_tensor.numpy())

    # MAE와 MAPE 계산
    mae = mean_absolute_error(y_test_inverse, pred_inverse)
    mape = mean_absolute_percentage_error(y_test_inverse, pred_inverse)
    print('MAE:', mae)
    print('MAPE:', mape)

      
