from django import template

from core.presentation import portfolio_text

register = template.Library()
register.filter("portfolio_text", portfolio_text)
