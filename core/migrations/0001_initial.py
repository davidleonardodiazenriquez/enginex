from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Asset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("location", models.CharField(max_length=180)),
                ("asset_class", models.CharField(max_length=120)),
                ("developer", models.CharField(max_length=120)),
                ("buildings", models.PositiveIntegerField()),
                ("units", models.PositiveIntegerField()),
                ("unit_mix", models.CharField(max_length=160)),
                ("amenities", models.TextField()),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="PortfolioMetrics",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("due_completed_pct", models.DecimalField(decimal_places=2, max_digits=5)),
                ("due_completed_value", models.DecimalField(decimal_places=2, max_digits=12)),
                ("due_incomplete_value", models.DecimalField(decimal_places=2, max_digits=12)),
                ("upcoming_signed_pct", models.DecimalField(decimal_places=2, max_digits=5)),
                ("upcoming_signed_value", models.DecimalField(decimal_places=2, max_digits=12)),
                ("upcoming_unsigned_value", models.DecimalField(decimal_places=2, max_digits=12)),
                ("reversionary_pct", models.DecimalField(decimal_places=2, max_digits=5)),
                ("in_place_rent", models.DecimalField(decimal_places=2, max_digits=12)),
                ("market_rent", models.DecimalField(decimal_places=2, max_digits=12)),
                ("asset", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="metrics", to="core.asset")),
            ],
            options={"verbose_name_plural": "portfolio metrics"},
        ),
        migrations.CreateModel(
            name="TenantRevenue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rank", models.PositiveSmallIntegerField()),
                ("tenant_name", models.CharField(max_length=120)),
                ("revenue_share", models.DecimalField(decimal_places=2, max_digits=5)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tenant_revenues", to="core.asset")),
            ],
            options={"ordering": ["rank"]},
        ),
        migrations.CreateModel(
            name="Vacancy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rank", models.PositiveSmallIntegerField()),
                ("unit_name", models.CharField(max_length=120)),
                ("revenue_share", models.DecimalField(decimal_places=2, max_digits=5)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vacancies", to="core.asset")),
            ],
            options={"ordering": ["rank"]},
        ),
        migrations.AddConstraint(
            model_name="tenantrevenue",
            constraint=models.UniqueConstraint(fields=("asset", "rank"), name="unique_asset_tenant_rank"),
        ),
        migrations.AddConstraint(
            model_name="vacancy",
            constraint=models.UniqueConstraint(fields=("asset", "rank"), name="unique_asset_vacancy_rank"),
        ),
    ]
