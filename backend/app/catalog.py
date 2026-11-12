from .models import Product

CATALOG: list[Product] = [
    Product(id="demo-headphones-1", name="Sony WH-1000XM5", category="headphones", merchant="Audio Gallery", price_minor=34800, features=["noise cancellation", "30-hour battery", "multipoint"]),
    Product(id="demo-headphones-2", name="Bose QuietComfort", category="headphones", merchant="Audio Gallery", price_minor=29900, features=["noise cancellation", "comfortable", "24-hour battery"]),
    Product(id="demo-laptop-1", name="MacBook Pro 14-inch", category="laptop", merchant="DemoTech Store", price_minor=219900, features=["M-series chip", "14-inch display", "18-hour battery"]),
    Product(id="demo-chair-1", name="Ergonomic office chair", category="chair", merchant="Workspace Lab", price_minor=69900, features=["lumbar support", "adjustable arms", "mesh back"]),
    Product(id="demo-cloud-1", name="Cloud storage annual plan", category="software", merchant="CloudNest", price_minor=12000, recurring_cost_minor=12000, features=["2TB storage", "annual renewal"]),
]
