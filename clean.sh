#!/bin/bash

# Остановка и удаление всех контейнеров
echo "Остановка всех контейнеров..."
sudo docker stop $(sudo docker ps -aq)

echo "Удаление всех контейнеров..."
sudo docker rm $(sudo docker ps -aq)

# Удаление всех образов
echo "Удаление всех образов..."
sudo docker rmi $(sudo docker images -q)

# Удаление всех томов
echo "Удаление всех томов..."
sudo docker volume rm $(sudo docker volume ls -q)

echo "Все контейнеры образы и томы удалены."