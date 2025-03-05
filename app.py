import streamlit as st
import requests
from datetime import datetime
from typing import List, Dict

# PRICE = 'value'

st.set_page_config(page_title="Travel Planner", page_icon="✈️")

def find_flights(api_token: str, params: Dict) -> List[Dict]:
    base_params = {
        'origin': params['origin'],
        'destination': params['destination'],
        'departure_at': params['dates'][0],
        'return_at': params['dates'][1],
        'currency': 'rub',
        'token': api_token,
        # 'trip_class': params['trip_class'],
        'direct': "true" if params['direct'] else "false",
        'sorting': 'price',
        'limit': 100,
    }

    try:
        response = requests.get(
            'https://api.travelpayouts.com/aviasales/v3/prices_for_dates',
            params={k: v for k, v in base_params.items() if v is not None},
            headers={'Accept-Encoding': 'gzip, deflate'},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get('data'):
            st.warning("Нет данных о рейсах для указанных параметров")
            return []

        flights = []
        for flight in data['data']:
            departure_at = datetime.fromisoformat(flight['departure_at'].replace('Z', '+00:00'))
            return_at = datetime.fromisoformat(flight['return_at'].replace('Z', '+00:00')) if flight.get('return_at') else None
            
            flight_data = {
                'origin': flight['origin'],
                'destination': flight['destination'],
                'departure_at': departure_at,
                'return_at': return_at,
                'origin_airport': flight.get('origin_airport', 'N/A'),
                'destination_airport': flight.get('destination_airport', 'N/A'),
                'price': flight['price'] * params['passengers'],
                'airline': flight.get('airline', 'Неизвестно'),
                # 'trip_class': params['trip_class'],
                'flight_number': flight.get('flight_number', 'N/A'),
                'transfers': flight.get('transfers', 0),
                'return_transfers': flight.get('return_transfers', 0),
                'duration': flight.get('duration', 0),
                'duration_to': flight.get('duration_to', 0),
                'duration_back': flight.get('duration_back', 0),
                'link': f"https://www.aviasales.com{flight['link']}"
            }
            
            flights.append(flight_data)
            
        return flights[:100]
        
    except Exception as e:
        st.error(f"Ошибка поиска рейсов: {str(e)}")
        return []

def find_hotels(api_token: str, params: Dict) -> List[Dict]:
    hotel_params = {
        'location': params['destination'],
        'checkIn': params['dates'][0],
        'checkOut': params['dates'][1],
        'adults': params['passengers'],
        'currency': 'rub',
        'token': api_token,
        'limit': 20,
        'sortBy': 'value'
        # 'sortBy': 'price'
    }

    try:
        response = requests.get(
            'https://engine.hotellook.com/api/v2/cache.json',
            params=hotel_params,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        check_in_date = datetime.strptime(params['dates'][0], '%Y-%m-%d')
        check_out_date = datetime.strptime(params['dates'][1], '%Y-%m-%d')
        nights = (check_out_date - check_in_date).days
        
        hotels = [{
            'name': item.get('hotelName', 'Без названия'),
            'price': item.get('priceFrom', item.get('priceAvg', 0)),
            'stars': int(item.get('stars', 0)),
            'nights': nights
        } for item in data]

        filtered_hotels = [h for h in hotels if h['stars'] >= params.get('min_stars', 0)]

        filtered_hotels.sort(key=lambda x: (-x['stars'], x['price']))
        
        return filtered_hotels[:100]
        
    except Exception as e:
        st.error(f"Ошибка поиска отелей: {str(e)}")
        return []

def create_packages(flights: List[Dict], hotels: List[Dict], params: Dict) -> List[Dict]:
    packages = []
    used_flights = set()  
    used_hotels = set()   
    

    sorted_flights = sorted(flights, key=lambda x: x['price'])
    sorted_hotels = sorted(hotels, key=lambda x: x['price'])
    
    for flight in sorted_flights:
        if flight['flight_number'] in used_flights:
            continue 
            
        for hotel in sorted_hotels:
            if hotel['name'] in used_hotels:
                continue 

            total = flight['price'] + hotel['price'] 
            
            packages.append({
                'flight': flight,
                'hotel': hotel,
                'total_price': total,
                'stars': hotel['stars'],
                # 'trip_class': flight['trip_class']
            })

            used_flights.add(flight['flight_number'])
            used_hotels.add(hotel['name'])
            break
    
    packages.sort(key=lambda x: x['total_price'])
    return packages

def show_results(packages: List[Dict], params: Dict):
    if not packages:
        st.warning("Подходящих вариантов не найдено 😔")
        return
    
    st.subheader("🏆 Топ-5 вариантов")
    # class_map = {0: "Эконом", 1: "Бизнес", 2: "Первый"}
    
    def hours_and_minutes(time):
        hours = time  % (60 * 24) // 60
        minutes = time % 60
        return f'{hours} часов {minutes} минут'

    for i, p in enumerate(packages[:5], 1):
        with st.expander(f"Вариант {i} | {p['total_price']:,.2f} RUB".replace(',', ' ')):
            cols = st.columns(3)
            with cols[0]:
                st.metric("✈️ Билет", f"{p['flight']['price']:,.2f} RUB".replace(',', ' '))
                # st.caption(f"Класс: {class_map[p['flight']['trip_class']]}")
                st.caption(f"{p['flight']['airline']} #{p['flight']['flight_number']}")
                st.caption(f"Количество пересадок туда: {p['flight']['transfers']} Количество пересадок обратно: {p['flight']['return_transfers']}")
                st.caption(f"Длительность перелета туда: {hours_and_minutes(p['flight']['duration_to'])} | Длительность перелета обратно: {hours_and_minutes(p['flight']['duration_back'])} ")
                st.caption(f" IATA-код аэропорта отправления: {p['flight']['origin_airport']}  IATA-код аэропорта прибытия: {p['flight']['destination_airport']}")
                st.caption(f"Вылет: {p['flight']['departure_at'].strftime('%d.%m.%Y %H:%M')}")
                
            with cols[1]:
                st.metric("🏨 Отель", f"{p['hotel']['price']} RUB/ночь")
                st.caption(f"{p['hotel']['name']}")
                st.caption(f"{p['hotel']['stars']}★")
                st.caption(f"{p['hotel']['nights']} ночей")
                
            with cols[2]:
                st.metric("💰 Итого", f"{p['total_price']:,.2f} RUB".replace(',', ' '))
                st.caption(f"👥 {params['passengers']} пассажиров")
                if p['flight'].get('link'):
                    st.markdown(f"[🔗 Посмотреть билет на Aviasales]({p['flight']['link']})")

def main():
    st.title("✈️ Планировщик путешествий")
    
    with st.form("search_form"):
        cols = st.columns(4)
        with cols[0]:
            origin = st.text_input("Откуда (IATA)", "MOW")
        with cols[1]:
            destination = st.text_input("Куда (IATA)", "PAR")
        with cols[2]:
            departure = st.date_input("Дата вылета", datetime(2025, 3, 1))
        with cols[3]:
            return_date = st.date_input("Дата возврата", datetime(2025, 3, 7))
        
        cols_filters = st.columns(3)
        with cols_filters[0]:
            passengers = st.number_input("Пассажиры", 1, 10, 1)
        with cols_filters[1]:
            max_price = st.number_input("Макс. бюджет (RUB)", 1000, 1000000, 300000)
            min_stars = st.selectbox("Звезды отеля", [0, 1, 2, 3, 4, 5], index=1) 
        with cols_filters[2]:
            direct = st.checkbox("Без пересадок", True) 
            
            # trip_class = st.radio("Класс", ["Эконом", "Бизнес", "Первый"], index=0)

        submitted = st.form_submit_button("Найти варианты")

    if submitted:
        params = {
            'origin': origin.upper(),
            'destination': destination.upper(),
            'dates': (departure.strftime('%Y-%m-%d'), 
                    return_date.strftime('%Y-%m-%d')),
            'passengers': passengers,
            'direct': direct,
            # 'trip_class': 0 if trip_class == "Эконом" else 1 if trip_class == "Бизнес" else 2,
            'min_stars': min_stars,
        }

        with st.spinner("🔍 Ищем лучшие варианты..."):
            api_token = "239af4a156ffb6d765d5661707e66f2f"
            
            flights = find_flights(api_token, params)
            hotels = find_hotels(api_token, params)
                
            packages = create_packages(flights, hotels, params)
            filtered = [p for p in packages if p['total_price'] <= max_price]
            
            if not filtered:
                st.warning("Подходящих вариантов не найдено 😔")

            show_results(filtered[:5], params)

if __name__ == "__main__":
    main()