from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import Product, ProductCategory, User, RoleEnum, Lead, LeadProduct, Conversion, ConversionItem
from app.schemas import (ProductCategoryCreate, ProductCategoryUpdate, ProductCategoryOut, ProductCreate, ProductUpdate, ProductOut, LeadProductCreate, LeadProductUpdate, LeadProductOut, ConversionCreate, ConversionOut)
from app.deps import get_current_user, require_roles, ALL_STAFF, LEADERS_UP, log_action
from app.routers.leads import _get_lead_or_404, _check_visibility

router = APIRouter(prefix="/api", tags=["products"])
PRODUCT_ADMINS = (RoleEnum.super_admin, RoleEnum.site_admin, RoleEnum.marketing_manager)

def _product_out(p):
    out=ProductOut.model_validate(p); out.category_name=p.category.name if p.category else None; return out
def _lp_out(x):
    out=LeadProductOut.model_validate(x); out.product_name=x.product.name if x.product else None; out.sku=x.product.sku if x.product else None; out.unit_price=x.product.price if x.product else None; out.currency=x.product.currency if x.product else None; return out

@router.get('/product-categories', response_model=list[ProductCategoryOut])
def categories(active_only: bool=True, current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    q=db.query(ProductCategory)
    if active_only: q=q.filter(ProductCategory.is_active==True)
    return q.order_by(ProductCategory.name).all()

@router.post('/product-categories', response_model=ProductCategoryOut)
def create_category(payload: ProductCategoryCreate, request: Request, current_user: User=Depends(require_roles(*PRODUCT_ADMINS)), db: Session=Depends(get_db)):
    if db.query(ProductCategory).filter(ProductCategory.name.ilike(payload.name.strip())).first(): raise HTTPException(409,'Category already exists')
    x=ProductCategory(name=payload.name.strip(),description=payload.description); db.add(x); db.commit(); db.refresh(x); log_action(db,current_user,'create_product_category','product_category',x.id,{'name':x.name},request); return x

@router.put('/product-categories/{category_id}', response_model=ProductCategoryOut)
def update_category(category_id:int,payload:ProductCategoryUpdate,request:Request,current_user:User=Depends(require_roles(*PRODUCT_ADMINS)),db:Session=Depends(get_db)):
    x=db.query(ProductCategory).get(category_id)
    if not x: raise HTTPException(404,'Category not found')
    for k,v in payload.model_dump(exclude_unset=True).items(): setattr(x,k,v.strip() if k=='name' and v else v)
    db.commit(); db.refresh(x); log_action(db,current_user,'update_product_category','product_category',x.id,payload.model_dump(exclude_unset=True),request); return x

@router.get('/products', response_model=list[ProductOut])
def list_products(search:str|None=None, active_only:bool=False, category_id:int|None=None, current_user:User=Depends(get_current_user), db:Session=Depends(get_db)):
    q=db.query(Product)
    if active_only: q=q.filter(Product.is_active==True)
    if category_id: q=q.filter(Product.category_id==category_id)
    if search:
        like=f'%{search}%'; q=q.filter(or_(Product.name.ilike(like),Product.sku.ilike(like)))
    return [_product_out(x) for x in q.order_by(Product.name).all()]

@router.post('/products', response_model=ProductOut)
def create_product(payload:ProductCreate,request:Request,current_user:User=Depends(require_roles(*PRODUCT_ADMINS)),db:Session=Depends(get_db)):
    if payload.sku and db.query(Product).filter(Product.sku==payload.sku).first(): raise HTTPException(409,'SKU already exists')
    if payload.category_id and not db.query(ProductCategory).filter(ProductCategory.id==payload.category_id).first(): raise HTTPException(404,'Category not found')
    x=Product(**payload.model_dump()); db.add(x); db.commit(); db.refresh(x); log_action(db,current_user,'create_product','product',x.id,{'name':x.name},request); return _product_out(x)

@router.put('/products/{product_id}', response_model=ProductOut)
def update_product(product_id:int,payload:ProductUpdate,request:Request,current_user:User=Depends(require_roles(*PRODUCT_ADMINS)),db:Session=Depends(get_db)):
    x=db.query(Product).get(product_id)
    if not x: raise HTTPException(404,'Product not found')
    data=payload.model_dump(exclude_unset=True)
    if data.get('sku') and db.query(Product).filter(Product.sku==data['sku'],Product.id!=x.id).first(): raise HTTPException(409,'SKU already exists')
    if data.get('category_id') and not db.query(ProductCategory).filter(ProductCategory.id==data['category_id']).first(): raise HTTPException(404,'Category not found')
    for k,v in data.items(): setattr(x,k,v)
    db.commit(); db.refresh(x); log_action(db,current_user,'update_product','product',x.id,data,request); return _product_out(x)

@router.delete('/products/{product_id}')
def delete_product(product_id:int,request:Request,current_user:User=Depends(require_roles(*PRODUCT_ADMINS)),db:Session=Depends(get_db)):
    x=db.query(Product).get(product_id)
    if not x: raise HTTPException(404,'Product not found')
    if db.query(LeadProduct).filter(LeadProduct.product_id==product_id).first() or db.query(ConversionItem).filter(ConversionItem.product_id==product_id).first(): raise HTTPException(409,'Product is already used; deactivate it instead')
    db.delete(x); db.commit(); log_action(db,current_user,'delete_product','product',product_id,request=request); return {'detail':'Product deleted'}

@router.get('/leads/{lead_id}/products', response_model=list[LeadProductOut])
def lead_products(lead_id:int,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    lead=_get_lead_or_404(db,lead_id); _check_visibility(current_user,lead); return [_lp_out(x) for x in db.query(LeadProduct).filter(LeadProduct.lead_id==lead_id).order_by(LeadProduct.created_at).all()]

@router.post('/leads/{lead_id}/products', response_model=LeadProductOut)
def add_lead_product(lead_id:int,payload:LeadProductCreate,request:Request,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    lead=_get_lead_or_404(db,lead_id); _check_visibility(current_user,lead)
    product=db.query(Product).filter(Product.id==payload.product_id,Product.is_active==True).first()
    if not product: raise HTTPException(404,'Active product not found')
    if payload.quantity<1: raise HTTPException(400,'Quantity must be at least 1')
    x=db.query(LeadProduct).filter(LeadProduct.lead_id==lead_id,LeadProduct.product_id==payload.product_id).first()
    if x:
        x.quantity=payload.quantity; x.interest_status=payload.interest_status; x.quoted_price=payload.quoted_price; x.notes=payload.notes
    else: x=LeadProduct(lead_id=lead_id,**payload.model_dump()); db.add(x)
    db.commit(); db.refresh(x); log_action(db,current_user,'add_lead_product','lead_product',x.id,{'lead_id':lead_id,'product_id':product.id},request); return _lp_out(x)

@router.put('/leads/{lead_id}/products/{item_id}', response_model=LeadProductOut)
def update_lead_product(lead_id:int,item_id:int,payload:LeadProductUpdate,request:Request,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    lead=_get_lead_or_404(db,lead_id); _check_visibility(current_user,lead); x=db.query(LeadProduct).filter(LeadProduct.id==item_id,LeadProduct.lead_id==lead_id).first()
    if not x: raise HTTPException(404,'Lead product not found')
    data=payload.model_dump(exclude_unset=True)
    if data.get('quantity',1)<1: raise HTTPException(400,'Quantity must be at least 1')
    for k,v in data.items(): setattr(x,k,v)
    db.commit(); db.refresh(x); return _lp_out(x)

@router.delete('/leads/{lead_id}/products/{item_id}')
def delete_lead_product(lead_id:int,item_id:int,request:Request,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    lead=_get_lead_or_404(db,lead_id); _check_visibility(current_user,lead); x=db.query(LeadProduct).filter(LeadProduct.id==item_id,LeadProduct.lead_id==lead_id).first()
    if not x: raise HTTPException(404,'Lead product not found')
    db.delete(x); db.commit(); log_action(db,current_user,'remove_lead_product','lead_product',item_id,request=request); return {'detail':'Product removed'}

@router.post('/leads/{lead_id}/convert', response_model=ConversionOut)
def convert_lead(lead_id:int,payload:ConversionCreate,request:Request,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    lead=_get_lead_or_404(db,lead_id); _check_visibility(current_user,lead)
    if not payload.items: raise HTTPException(400,'At least one product is required')
    if db.query(Conversion).filter(Conversion.lead_id==lead_id).first(): raise HTTPException(409,'Lead already has a conversion')
    items=[]; subtotal=0; tax=0
    for i in payload.items:
        if i.quantity<1: raise HTTPException(400,'Quantity must be at least 1')
        p=db.query(Product).filter(Product.id==i.product_id).first()
        if not p: raise HTTPException(404,f'Product {i.product_id} not found')
        price=p.price if i.unit_price is None else i.unit_price; tp=p.tax_percent if i.tax_percent is None else i.tax_percent
        line=price*i.quantity; line_tax=round(line*tp/100); subtotal+=line; tax+=line_tax
        items.append((p,i.quantity,price,tp,line))
    discount=max(0,payload.discount); taxable=max(0,subtotal-discount); tax=round(sum(round((price*q)*tp/100) for p,q,price,tp,line in items) * (taxable/subtotal if subtotal else 0)) if subtotal else 0
    total=taxable+tax
    c=Conversion(lead_id=lead_id,converted_by_id=current_user.id,conversion_date=payload.conversion_date or __import__('datetime').datetime.utcnow(),subtotal=subtotal,discount=discount,tax=tax,total=total,notes=payload.notes)
    db.add(c); db.flush()
    for p,q,price,tp,line in items: db.add(ConversionItem(conversion_id=c.id,product_id=p.id,product_name=p.name,sku=p.sku,quantity=q,unit_price=price,tax_percent=tp,line_total=line))
    old=lead.status.value; lead.status=__import__('app.models',fromlist=['LeadStatusEnum']).LeadStatusEnum.converted; lead.converted_at=c.conversion_date
    from app.models import LeadStatusHistory
    db.add(LeadStatusHistory(lead_id=lead.id,old_status=old,new_status='converted',changed_by_id=current_user.id,note='Lead converted'))
    db.commit(); db.refresh(c); log_action(db,current_user,'convert_lead','lead',lead.id,{'conversion_id':c.id,'total':total},request); return c

@router.get('/leads/{lead_id}/conversion', response_model=ConversionOut)
def get_conversion(lead_id:int,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    lead=_get_lead_or_404(db,lead_id); _check_visibility(current_user,lead); c=db.query(Conversion).filter(Conversion.lead_id==lead_id).first()
    if not c: raise HTTPException(404,'Conversion not found')
    return c
